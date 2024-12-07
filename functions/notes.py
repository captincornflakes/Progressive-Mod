import discord
from discord.ext import commands
from discord import app_commands


class ManageNotes(commands.Cog):
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

     @app_commands.command(name="notes", description="View or edit a user's notes in the database")
     async def notes(
          self,
          interaction: discord.Interaction,
          action: str,
          user: discord.Member,
          new_notes: str = None,
     ):
          """
          Manage user notes in the database.

          Parameters:
          - action: "view" or "edit"
          - user: The target user
          - new_notes: The new notes to set (required for "edit")
          """
          self.reconnect_database()

          # Check if the user has permission to use this command
          if not await self.has_permission(interaction):
               await interaction.response.send_message(
                    "You do not have permission to use this command.", ephemeral=True
               )
               return

          guild_id = interaction.guild_id
          user_id = user.id

          if action.lower() == "view":
               # Fetch and display notes
               try:
                    self.cursor.execute(
                         "SELECT notes FROM users WHERE guild_id = %s AND user_id = %s",
                         (guild_id, user_id),
                    )
                    result = self.cursor.fetchone()

                    if result:
                         notes = result[0]
                         if not notes:
                              notes = "No notes available"
                    else:
                         notes = "No records found for this user."

                    await interaction.response.send_message(
                         f"**{user.mention}'s Notes:**\n{notes}", ephemeral=True
                    )
               except Exception as e:
                    await interaction.response.send_message(
                         f"Error fetching notes: {e}", ephemeral=True
                    )

          elif action.lower() == "edit":
               if not new_notes:
                    await interaction.response.send_message(
                         "You must provide new notes to update.", ephemeral=True
                    )
                    return

               # Update notes
               try:
                    self.cursor.execute(
                         "UPDATE users SET notes = %s WHERE guild_id = %s AND user_id = %s",
                         (new_notes, guild_id, user_id),
                    )
                    self.conn.commit()

                    await interaction.response.send_message(
                         f"Successfully updated notes for {user.mention}.", ephemeral=True
                    )
               except Exception as e:
                    await interaction.response.send_message(
                         f"Error updating notes: {e}", ephemeral=True
                    )

          else:
               await interaction.response.send_message(
                    "Invalid action. Use `view` or `edit`.", ephemeral=True
               )


async def setup(bot):
     await bot.add_cog(ManageNotes(bot))
