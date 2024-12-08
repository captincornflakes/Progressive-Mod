import discord
from discord.ext import commands, tasks
import json
from datetime import datetime
import asyncio


class PointDecay(commands.Cog):
     def __init__(self, bot):
          self.bot = bot
          self.conn = bot.db_connection
          self.point_decay_loop.start()

     def cog_unload(self):
          self.point_decay_loop.cancel()

     def reconnect_database(self):
          """Reconnect to the database if the connection is lost."""
          try:
               self.conn.ping(reconnect=True, attempts=3, delay=5)
          except Exception as e:
               print(f"Error reconnecting to the database: {e}")

     @tasks.loop(hours=24)
     async def point_decay_loop(self):
          """Loop to decrement user points over time."""
          self.reconnect_database()
          try:
               with self.conn.cursor() as cursor:
                    cursor.execute("SELECT user_id, guild_id, points, log_json FROM users")
                    users = cursor.fetchall()

               for user in users:
                    user_id, guild_id, points, log_json = user

                    # Decode and validate log_json
                    if isinstance(log_json, str):
                         try:
                              log_json = json.loads(log_json)
                         except json.JSONDecodeError:
                              print(f"Skipping user {user_id}: invalid JSON format in log_json.")
                              log_json = {}

                    if not isinstance(log_json, dict):
                         print(f"Skipping user {user_id}: log_json is not a dictionary.")
                         continue

                    # Decay points if they are above zero
                    if points > 0:
                         new_points = max(0, points - 10)
                         log_entry = {
                         "action": "point_decay",
                         "points_removed": 10,
                         "timestamp": datetime.now().isoformat(),
                         }

                         # Add the log entry
                         log_json.setdefault("log_entries", []).append(log_entry)

                         # Update database
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
          """Ensure the bot is ready before starting the loop."""
          await self.bot.wait_until_ready()

     @commands.command(name="show_log", help="Show the log for a specific user.")
     async def show_log(self, ctx, member: discord.Member):
          """Display a user's log information."""
          self.reconnect_database()
          try:
               with self.conn.cursor() as cursor:
                    cursor.execute(
                         "SELECT points, log_json FROM users WHERE user_id = %s AND guild_id = %s",
                         (member.id, ctx.guild.id),
                    )
                    result = cursor.fetchone()

               if not result:
                    await ctx.send(f"No data found for {member.mention}.")
                    return

               points, log_json = result

               # Decode log_json
               if isinstance(log_json, str):
                    try:
                         log_json = json.loads(log_json)
                    except json.JSONDecodeError:
                         await ctx.send("Error decoding log JSON for this user.")
                         return

               if not isinstance(log_json, dict):
                    await ctx.send("Invalid log data format for this user.")
                    return

               # Format log entries
               log_entries = log_json.get("log_entries", [])
               formatted_logs = "\n".join(
                    [
                         f"- **{entry.get('timestamp', 'Unknown')}**: {entry.get('action', 'Unknown action')} (Points removed: {entry.get('points_removed', 'N/A')})"
                         for entry in log_entries
                    ]
               )

               response = (
                    f"**User:** {member.mention}\n"
                    f"**Points:** {points}\n"
                    f"**Log Entries:**\n{formatted_logs if log_entries else 'No log entries found.'}"
               )

               await ctx.send(response)

          except Exception as e:
               print(f"Error fetching log for {member.id}: {e}")
               await ctx.send("An error occurred while retrieving the log.")

     @commands.command(name="force_decay", help="Force the point decay loop to run.")
     @commands.has_permissions(administrator=True)
     async def force_decay(self, ctx):
          """Force the point decay loop to run manually."""
          await self.point_decay_loop()
          await ctx.send("Point decay loop executed manually.")


async def setup(bot):
     await bot.add_cog(PointDecay(bot))
