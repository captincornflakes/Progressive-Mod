import discord
from discord.ext import commands
from discord import app_commands
import json
from datetime import datetime

class InstantBan(commands.Cog):
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
     
     @app_commands.command(name="ban", description="Instantly ban a user and log the action.")
     async def ban(self, interaction: discord.Interaction, user: discord.Member, reason: str = "No reason provided"):
          
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
                    await interaction.response.send_message("You do not have permission to ban members.", ephemeral=True)
                    return

               # Fetch user data from the database to update log_json
               self.cursor = self.bot.db_connection.cursor()
               self.cursor.execute("SELECT log_json FROM users WHERE user_id = %s AND guild_id = %s", (user.id, guild.id))
               result = self.cursor.fetchone()

               if result:
                    log_json = json.loads(result[0]) if result[0] else []
                    log_entry = {
                         "action_by": interaction.user.id,
                         "action_by_name": str(interaction.user),
                         "action": "Banned",
                         "timestamp": datetime.now().isoformat(),
                         "note": reason
                    }
                    log_json.append(log_entry)

                    # Update the log_json in the database
                    self.cursor.execute("UPDATE users SET log_json = %s WHERE user_id = %s AND guild_id = %s",
                                        (json.dumps(log_json), user.id, guild.id))
                    self.bot.db_connection.commit()
                    
                    # Ban the user
                    await guild.ban(user, reason=reason)
                    await interaction.response.send_message(f"{user.mention} has been banned.", ephemeral=True)
               else:
                    # If user not found in the database, handle this scenario
                    await interaction.response.send_message(f"No user with ID {user.id} found in the system, Please add a infraction first before you can ban them.", ephemeral=True)

          except Exception as e:
               await interaction.response.send_message(f"An error occurred while trying to ban the user: {e}", ephemeral=True)

async def setup(bot):
     await bot.add_cog(InstantBan(bot))
