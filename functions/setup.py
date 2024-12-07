import discord
from discord.ext import commands
from discord import app_commands

class BotSetup(commands.Cog):
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
     
     def store_role_in_db(self, guild_id, role_id):
          """Stores or updates the mod_role_id in the guild_settings table."""
          try:
               # Check if the guild_id already exists in the table
               self.cursor.execute("SELECT 1 FROM guild_settings WHERE guild_id = %s", (guild_id,))
               exists = self.cursor.fetchone()

               if exists:
                    # Update the mod_role_id for the guild
                    self.cursor.execute(
                         "UPDATE guild_settings SET mod_role_id = %s WHERE guild_id = %s",
                         (role_id, guild_id)
                    )
               else:
                    # Insert a new record for the guild
                    self.cursor.execute(
                         "INSERT INTO guild_settings (guild_id, mod_role_id) VALUES (%s, %s)",
                         (guild_id, role_id)
                    )

               self.conn.commit()
          except Exception as e:
               print(f"Error storing role in database for guild {guild_id}: {e}")

     @app_commands.command(name="setup", description="Sets up the bot with a progressive-moderator role.")
     async def setup(self, interaction: discord.Interaction):
          """Command to create a progressive-moderator role only if it does not already exist."""
          self.reconnect_database()
          
          # Check if the user has permission to use this command
          if not await self.has_permission(interaction):
               await interaction.response.send_message(
                    "You do not have permission to use this command.", ephemeral=True
               )
               return
          
          guild = interaction.guild

          # Check if the role already exists
          existing_role = discord.utils.get(guild.roles, name="progressive-moderator")
          if existing_role:
               self.store_role_in_db(guild.id, existing_role.id)
               await interaction.response.send_message(
                    "The 'progressive-moderator' role already exists and is stored in the database.", ephemeral=True
               )
               return

          # Create the progressive-moderator role if it doesn't exist
          permissions = discord.Permissions()
          permissions.update(manage_messages=True, ban_members=True, kick_members=True, manage_roles=True)

          try:
               new_role = await guild.create_role(
                    name="progressive-moderator", 
                    permissions=permissions, 
                    reason="Created for progressive moderators",
                    mentionable=True
               )
               self.store_role_in_db(guild.id, new_role.id)
               await interaction.response.send_message(
                    f"Created the 'progressive-moderator' role with permissions and stored it in the database.", ephemeral=True
               )
          except Exception as e:
               await interaction.response.send_message(f"An error occurred while creating the role: {e}", ephemeral=True)

     @commands.Cog.listener()
     async def on_guild_join(self, guild: discord.Guild):
          """Listener that runs when the bot joins a new guild."""
          self.reconnect_database()

          # Check if the 'progressive-moderator' role already exists
          existing_role = discord.utils.get(guild.roles, name="progressive-moderator")
          if existing_role:
               self.store_role_in_db(guild.id, existing_role.id)
               return

          permissions = discord.Permissions()
          permissions.update(manage_messages=True, ban_members=True, kick_members=True, manage_roles=True)

          try:
               # Create the role
               new_role = await guild.create_role(
                    name="progressive-moderator", 
                    permissions=permissions, 
                    reason="Created for progressive moderators",
                    mentionable=True
               )
               self.store_role_in_db(guild.id, new_role.id)
          except Exception as e:
               print(f"Error while creating role in {guild.name}: {e}")

async def setup(bot):
     await bot.add_cog(BotSetup(bot))
