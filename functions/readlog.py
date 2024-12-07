import discord
import json
from discord.ext import commands
from discord import app_commands

class ViewInfractions(commands.Cog):
     def __init__(self, bot):
          self.bot = bot
          self.conn = bot.db_connection
          self.cursor = self.conn.cursor()

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
     
     @app_commands.command(name="view", description="View a user's points, status, notes, and log_json from the database")
     async def view(self, interaction: discord.Interaction, user: discord.Member):
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

               # Fetch points, status, notes, and log_json for the user
               try:
                    self.cursor.execute(
                         "SELECT points, status, notes, log_json FROM users WHERE guild_id = %s AND user_id = %s",
                         (guild_id, user_id)
                    )
                    result = self.cursor.fetchone()

                    if result:
                         current_points, status, notes, log_json = result

                         if log_json is None:
                              log_json = "No logs available"
                         else:
                         # Parse the JSON and prepare it for display in a table format
                              try:
                                   log_entries = json.loads(log_json)
                                   formatted_log_json = "\n".join(
                                        [f"**Action By**: {entry['action_by_name']}\n**Points Added**: {entry['points_added']}\n**Note**: {entry['note']}\n**Timestamp**: {entry['timestamp']}\n" for entry in log_entries]
                                   )
                              except json.JSONDecodeError:
                                   formatted_log_json = "Failed to decode log_json"

                         if notes is None:
                              notes = "No notes available"
                    else:
                         current_points = 0
                         status = "No records found"
                         notes = "No notes available"
                         formatted_log_json = "No logs available"

               except Exception as e:
                    await interaction.response.send_message(f"Error while fetching data: {e}", ephemeral=True)
                    return

               # Send points, status, notes, and log_json to the user
               await interaction.response.send_message(
                    f"**{user.mention}'s Current Info:**\n"
                    f"Points: {current_points}\n"
                    f"Status: {status}\n"
                    f"Notes: {notes}\n"
                    f"Log Entries:\n{formatted_log_json}",
                    ephemeral=True
               )

          except Exception as e:
               await interaction.response.send_message(f"An error occurred: {e}", ephemeral=True)

async def setup(bot):
     await bot.add_cog(ViewInfractions(bot))
