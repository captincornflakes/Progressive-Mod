import discord
from discord.ext import commands, tasks
import json
from datetime import datetime, timedelta
import asyncio


class PointDecay(commands.Cog):
     def __init__(self, bot):
          self.bot = bot
          self.conn = bot.db_connection
          self.default_points = 0
          self.point_decay_loop.start()

     def reconnect_database(self):
          """Reconnect to the database if needed."""
          try:
               self.conn.ping(reconnect=True, attempts=3, delay=5)
          except Exception as e:
               print(f"Error reconnecting to the database: {e}")

     async def send_warning(self, user_id, guild_id, points, log_json):
          """Send a warning message to a user based on their points."""
          tiers = [
               {"points": 300, "status": "flagged", "message": "You have incurred significant infractions. Please adhere to the rules to avoid further consequences."},
               {"points": 500, "status": "risking ban", "message": "Your infractions are severe. You are at risk of being banned if your points reach 1000."},
               {"points": 1000, "status": "banned", "message": "Due to repeated violations of the rules, you have been banned from the server."},
          ]

          user = await self.bot.fetch_user(user_id)
          if user:
               for tier in tiers:
                    if points >= tier["points"]:
                         if "message_sent" not in log_json or log_json["message_sent"] != tier["status"]:
                              formatted_log = "\n".join(
                                   [
                                        f"• **Action**: {entry.get('action', 'N/A')} | **Word**: {entry.get('word', 'N/A')} | **Points Added**: {entry.get('points_added', 'N/A')} | **Time**: {entry.get('timestamp', 'N/A')}"
                                        for entry in log_json.get("log_entries", [])
                                   ]
                              )
                         message = (
                              f"{tier['message']}\n\n**Current Points**: {points}\n\n"
                              f"**Infraction Log:**\n{formatted_log or 'No infractions recorded.'}"
                         )
                         try:
                              await user.send(message)
                              print(f"Sent warning to user {user_id} in guild {guild_id}: {message}")
                              log_json["message_sent"] = tier["status"]
                         except discord.errors.Forbidden:
                              print(f"Unable to send DM to user {user_id}. They may have DMs disabled.")

                         if points >= 1000:
                              guild = self.bot.get_guild(guild_id)
                              if guild:
                                   member = guild.get_member(user_id)
                                   if member:
                                        await member.ban(reason="Exceeded maximum infractions (1000 points).")
                                        print(f"Banned user {user_id} in guild {guild_id} for reaching 1000 points.")
                                        log_json["ban_message"] = "User banned due to exceeding infraction points."
                              break
          return log_json

     @tasks.loop(minutes=15)
     async def point_decay_loop(self):
          """Decrement user points over time."""
          self.reconnect_database()
          try:
               with self.conn.cursor() as cursor:
                    cursor.execute("SELECT user_id, guild_id, points, log_json FROM users")
                    users = cursor.fetchall()

               for user in users:
                    user_id, guild_id, points, log_json = user

                    if isinstance(log_json, str):
                         try:
                              log_json = json.loads(log_json)
                         except json.JSONDecodeError:
                              print(f"Skipping user {user_id}: invalid JSON format in log_json.")
                              log_json = {}

                    if not isinstance(log_json, dict):
                         print(f"Skipping user {user_id}: log_json is not a dictionary.")
                         continue

                    if points > 0:
                         new_points = max(0, points - 10)
                         log_entry = {
                         "action": "point_decay",
                         "points_removed": 10,
                         "timestamp": datetime.now().isoformat(),
                         }

                         log_json.setdefault("log_entries", []).append(log_entry)

                         with self.conn.cursor() as cursor:
                              cursor.execute(
                                   "UPDATE users SET points = %s, log_json = %s WHERE user_id = %s AND guild_id = %s",
                                   (new_points, json.dumps(log_json), user_id, guild_id),
                              )
                         self.conn.commit()

                         print(f"Applied point decay to user {user_id}. New points: {new_points}")

          except Exception as e:
               print(f"Error in point_decay_loop: {e}")

     @point_decay_loop.before_loop
     async def before_point_decay_loop(self):
          """Wait until the next full hour before starting the loop."""
          now = datetime.now()
          next_quarter = now + timedelta(minutes=15 - now.minute % 15, seconds=-now.second, microseconds=-now.microsecond)
          await discord.utils.sleep_until(next_quarter)
          print("Point decay loop will start now.")


async def setup(bot):
     await bot.add_cog(PointDecay(bot))
