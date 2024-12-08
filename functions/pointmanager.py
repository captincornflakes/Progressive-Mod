import discord
from discord.ext import commands, tasks
import json
from datetime import datetime

class PointDecay(commands.Cog):
     def __init__(self, bot):
          self.bot = bot
          self.conn = bot.db_connection
          self.cursor = self.conn.cursor()
          self.default_points = 0
          self.point_decay_loop.start()  # Start the loop when the cog is loaded

     def reconnect_database(self):
          """Reconnects to the database if needed."""
          try:
               self.conn.ping(reconnect=True, attempts=3, delay=5)
          except Exception as e:
               print(f"Error reconnecting to the database: {e}")
          try:
               self.cursor.execute("SELECT 1")
               result = self.cursor.fetchone()
          except Exception as e:
               print(f"Error: Database connection failed: {e}")

     async def send_warning(self, user_id, guild_id, points, log_json):
          """Send a warning message to a user based on their points."""
          # Define the tiers and their respective messages
          tiers = [
               {
                    "points": 300,
                    "status": "flagged",
                    "message": "You have incurred significant infractions. Please adhere to the rules to avoid further consequences."
               },
               {
                    "points": 500,
                    "status": "risking ban",
                    "message": "Your infractions are severe. You are at risk of being banned if your points reach 1000."
               },
               {
                    "points": 1000,
                    "status": "banned",
                    "message": "Due to repeated violations of the rules, you have been banned from the server."
               },
                    ]

          user = await self.bot.fetch_user(user_id)
          if user:
               for tier in tiers:
                    if points >= tier["points"]:
                         # Check if the message for this tier has already been sent
                         if "message_sent" not in log_json or log_json["message_sent"] != tier["status"]:
                              # Format the infraction log nicely
                              formatted_log = "\n".join(
                              [f"• **Action**: {entry.get('action', 'N/A')} | **Word**: {entry.get('word', 'N/A')} | **Points Added**: {entry.get('points_added', 'N/A')} | **Time**: {entry.get('timestamp', 'N/A')}"
                                   for entry in log_json.get("log_entries", [])]
                              )
                              message = (
                              f"{tier['message']}\n\n**Current Points**: {points}\n\n"
                              f"**Infraction Log:**\n{formatted_log or 'No infractions recorded.'}"
                              )
                              try:
                                   # Send DM to the user
                                   await user.send(message)
                                   print(f"Sent warning to user {user_id} in guild {guild_id}: {message}")

                                   # Update the log to mark this tier's message as sent
                                   log_json["message_sent"] = tier["status"]

                              except discord.errors.Forbidden:
                                   print(f"Unable to send DM to user {user_id}. They may have DMs disabled.")

                         # If points are 1000 or more, ban the user
                         if points >= 1000:
                              guild = self.bot.get_guild(guild_id)
                              if guild:
                                   member = guild.get_member(user_id)
                              if member:
                                   await member.ban(reason="Exceeded maximum infractions (1000 points).")
                                   print(f"Banned user {user_id} in guild {guild_id} for reaching 1000 points.")
                                   # Update the log to record the ban
                                   log_json["ban_message"] = "User banned due to exceeding infraction points."

                         break  # Stop checking further tiers once the applicable one is found

          # Return the updated log_json for database updates
          return log_json


     @tasks.loop(hours=1)
     async def point_decay_loop(self):
          """Loop that runs every hour on the hour and reduces points for all users by 10."""
          
          # Define the tiers and messages
          tiers = [
               {"points": 300, "status": "flagged", "message": "You have incurred significant infractions. You are at risk of being banned once you reach 1000 points."},
               {"points": 500, "status": "risking ban", "message": "You have incurred significant infractions. You are at risk of being banned once you reach 1000 points."},
               {"points": 1000, "status": "banned", "message": "Due to repeated violations of the rules, you have been banned from the server."}
          ]
          
          try:
               current_time = datetime.now().isoformat()
               print(f"Point decay started at {current_time}")

               # Reconnect to the database before running the operation
               self.reconnect_database()

               # Fetch all users' current points
               self.cursor.execute("SELECT guild_id, user_id, points, log_json, status FROM users")
               users = self.cursor.fetchall()

               # Loop through all users and reduce their points by 10 if possible
               for guild_id, user_id, current_points, log_json, status in users:
                    new_points = max(0, current_points - 10)  # Ensure points don't go below 0
                    if new_points != current_points:
                         # Update the user's points in the database
                         self.cursor.execute(
                         "UPDATE users SET points = %s WHERE guild_id = %s AND user_id = %s",
                         (new_points, guild_id, user_id)
                         )
                         print(f"Reduced points for user {user_id} in guild {guild_id}: {current_points} -> {new_points}")

                         # Load the log data if available
                         log_json = json.loads(log_json) if log_json else {}

                         # Check for warning thresholds after updating points
                         log_json = await self.send_warning(user_id, guild_id, new_points, log_json)

                         # Update status based on points thresholds
                         new_status = "active"  # Default status for users under 300 points
                         for tier in tiers:
                              if new_points >= tier["points"]:
                                   new_status = tier["status"]

                         # Update the status in the database if changed
                         if new_status != status:
                              self.cursor.execute(
                                   "UPDATE users SET status = %s WHERE guild_id = %s AND user_id = %s",
                                   (new_status, guild_id, user_id)
                              )
                         print(f"Updated status for user {user_id} in guild {guild_id}: {status} -> {new_status}")

                         # Update log_json in the database if modified
                         self.cursor.execute(
                         "UPDATE users SET log_json = %s WHERE guild_id = %s AND user_id = %s",
                         (json.dumps(log_json), guild_id, user_id)
                         )

               # Commit changes
               self.conn.commit()

          except Exception as e:
               print(f"Error in point_decay_loop: {e}")

     @point_decay_loop.before_loop
     async def before_point_decay_loop(self):
          """Ensure that the loop runs at the top of the hour."""
          from datetime import datetime, timedelta
          now = datetime.now()
          # Calculate the time until the next hour
          next_hour = (now.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1))
          await discord.utils.sleep_until(next_hour)
          print("Point decay loop will start now.")

async def setup(bot):
     await bot.add_cog(PointDecay(bot))
