import discord
import json
from discord.ext import commands
from discord import app_commands
from datetime import datetime


class InfractionManagement(commands.Cog):
     def __init__(self, bot):
          self.bot = bot
          self.conn = bot.db_connection
          self.cursor = self.conn.cursor()
          self.default_points = 0

     def reconnect_database(self):
          """Reconnects to the database if needed."""
          try:
               self.conn.ping(reconnect=True, attempts=3, delay=5)
          except Exception as e:
               print(f"Error reconnecting to the database: {e}")
          try:
               self.cursor.execute("SELECT 1")
               result = self.cursor.fetchone()
               print("Debug: Database connection is active.")
          except Exception as e:
               print(f"Debug: Database connection failed: {e}")

     async def has_permission(self, interaction: discord.Interaction) -> bool:
          """Check if the user is an admin or has the mod role from the database."""
          guild_id = interaction.guild_id
          user = interaction.user

          # Check if the user is an admin
          if user.guild_permissions.administrator:
               return True

          # Check if the user has the mod role
          try:
               self.cursor.execute(
                    "SELECT mod_role_id FROM guild_settings WHERE guild_id = %s",
                    (guild_id,),
               )
               result = self.cursor.fetchone()
               if result:
                    mod_role_id = result[0]
                    mod_role = interaction.guild.get_role(mod_role_id)
                    if mod_role and mod_role in user.roles:
                         return True
          except Exception as e:
               print(f"Error checking permissions: {e}")
          return False

     @app_commands.command(name="infraction", description="Add or update a user's infraction record in the database")
     async def infraction(self, interaction: discord.Interaction, user: discord.Member, points: int, note: str):
          self.reconnect_database()

          # Check if the user has permission to use this command
          if not await self.has_permission(interaction):
               await interaction.response.send_message(
                    "You do not have permission to use this command.", ephemeral=True
               )
               return

          try:
               guild_id = interaction.guild_id
               user_id = user.id

               # Fetch existing record
               try:
                    self.cursor.execute(
                         "SELECT points, log_json FROM users WHERE guild_id = %s AND user_id = %s",
                         (guild_id, user_id),
                    )
                    result = self.cursor.fetchone()

                    if result:
                         current_points, log_json = result
                         new_points = current_points + points
                    else:
                         current_points = self.default_points
                         log_json = None
                         new_points = points

               except Exception as e:
                    await interaction.response.send_message(f"Error while fetching data: {e}", ephemeral=True)
                    return

               # Prepare log entry
               current_time = datetime.now().isoformat()
               log_entry = {
                    "action_by": interaction.user.id,
                    "action_by_name": str(interaction.user),
                    "points_added": points,
                    "note": note,
                    "timestamp": current_time,
               }

               if result:
                    # User exists, update data but don't change notes
                    updated_log = json.loads(log_json) if log_json else []
                    updated_log.append(log_entry)
                    self.cursor.execute(
                         "UPDATE users SET points = %s, log_json = %s WHERE guild_id = %s AND user_id = %s",
                         (new_points, json.dumps(updated_log), guild_id, user_id),
                    )
                    await interaction.response.send_message(
                         f"Updated {user.mention}: New points total is {new_points}.", ephemeral=True
                    )
               else:
                    # User not found, insert new data
                    new_log = [log_entry]
                    self.cursor.execute(
                         "INSERT INTO users (guild_id, user_id, status, points, log_json, notes) VALUES (%s, %s, %s, %s, %s, %s)",
                         (guild_id, user_id, "active", points, json.dumps(new_log), ""),
                    )
                    await interaction.response.send_message(
                         f"Added {user.mention} to the database with {points} points.", ephemeral=True
                    )

               self.conn.commit()

          except Exception as e:
               await interaction.response.send_message(f"An error occurred: {e}", ephemeral=True)


async def setup(bot):
     await bot.add_cog(InfractionManagement(bot))
