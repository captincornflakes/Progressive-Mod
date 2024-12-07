import discord
from discord.ext import commands
from discord import app_commands
import json
from datetime import datetime

class UnbanUser(commands.Cog):
     def __init__(self, bot):
          self.bot = bot

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
     
     @app_commands.command(name="unban", description="Unban a user from the server by user ID.")
     async def unban(self, interaction: discord.Interaction, user_id: int):
          """Unban a user from the guild using their user ID."""

          # Check if the user has permission to use this command
          if not await self.has_permission(interaction):
               await interaction.response.send_message(
                    "You do not have permission to use this command.", ephemeral=True
               )
               return
          
          try:
               # Get the guild from the interaction
               guild = interaction.guild

               # Check if the user has 'ban_members' permission
               if not interaction.user.guild_permissions.ban_members:
                    await interaction.response.send_message("You do not have permission to unban members.", ephemeral=True)
                    return

               # Try to unban the user by ID
               banned_users = await guild.bans()
               user_to_unban = discord.Object(id=user_id)

               # Check if the user is banned
               if any(ban.user.id == user_id for ban in banned_users):
                    await guild.unban(user_to_unban)
                    await interaction.response.send_message(f"User with ID {user_id} has been unbanned.", ephemeral=True)

                    # Fetch user data from the database to update log_json
                    self.cursor = self.bot.db_connection.cursor()
                    self.cursor.execute("SELECT log_json FROM users WHERE user_id = %s AND guild_id = %s", (user_id, guild.id))
                    result = self.cursor.fetchone()

                    if result:
                         log_json = json.loads(result[0]) if result[0] else []
                         log_entry = {
                         "action_by": interaction.user.id,
                         "action_by_name": str(interaction.user),
                         "action": "Unbanned",
                         "timestamp": datetime.now().isoformat(),
                         "note": "User has been unbanned from the server."
                         }
                         log_json.append(log_entry)

                         # Update the log_json in the database
                         self.cursor.execute("UPDATE users SET log_json = %s WHERE user_id = %s AND guild_id = %s",
                                             (json.dumps(log_json), user_id, guild.id))
                         self.bot.db_connection.commit()
                    else:
                         # If user not found in the database, handle this scenario
                         await interaction.response.send_message(f"No user with ID {user_id} found in the database.", ephemeral=True)

               else:
                    await interaction.response.send_message(f"No user with ID {user_id} is currently banned.", ephemeral=True)

          except Exception as e:
               await interaction.response.send_message(f"An error occurred while trying to unban the user: {e}", ephemeral=True)

async def setup(bot):
     await bot.add_cog(UnbanUser(bot))
