import discord
from discord.ext import commands
from discord import app_commands
import json
from datetime import datetime


class WordFilter(commands.Cog):
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

     def fetch_chat_words(self, guild_id):
          """Fetch the chat_words column from the guild_settings table."""
          try:
               self.cursor.execute(
                    "SELECT chat_words FROM guild_settings WHERE guild_id = %s",
                    (guild_id,),
               )
               result = self.cursor.fetchone()
               return json.loads(result[0]) if result and result[0] else {}
          except Exception as e:
               print(f"Error fetching chat_words: {e}")
               return {}

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
     
     def update_user_points(self, guild_id, user_id, word, points):
          try:
               # Fetch current user data
               self.cursor.execute(
                    "SELECT points, log_json FROM users WHERE guild_id = %s AND user_id = %s",
                    (guild_id, user_id),
               )
               result = self.cursor.fetchone()
               current_points = result[0] if result else 0
               log_json = json.loads(result[1]) if result and result[1] else []

               # Update points and log
               new_points = current_points + points
               log_entry = {
                    "action": "filtered_word_detected",
                    "word": word,
                    "points_added": points,
                    "timestamp": datetime.now().isoformat(),
                    "action_by_name": "Bot", 
                    "note": f"Modded by Progressive Bot - Chat Infraction word: {word}", 
               }
               log_json.append(log_entry)

               if result:
                    # Update existing record
                    self.cursor.execute(
                         "UPDATE users SET points = %s, log_json = %s WHERE guild_id = %s AND user_id = %s",
                         (new_points, json.dumps(log_json), guild_id, user_id),
                    )
               else:
                    # Create a new record
                    self.cursor.execute(
                         "INSERT INTO users (guild_id, user_id, status, points, log_json, notes) VALUES (%s, %s, %s, %s, %s, %s)",
                         (guild_id, user_id, "active", points, json.dumps([log_entry]), ""),
                    )
               self.conn.commit()
          except Exception as e:
               print(f"Error updating user points: {e}")
               
     def update_chat_words(self, guild_id, chat_words):
          """Update the chat_words column in the guild_settings table."""
          try:
               self.cursor.execute(
                    "UPDATE guild_settings SET chat_words = %s WHERE guild_id = %s",
                    (json.dumps(chat_words), guild_id),
               )
               self.conn.commit()
          except Exception as e:
               print(f"Error updating chat_words: {e}")

     @app_commands.command(name="filter", description="Manage filtered words for the server.")
     async def filter(
          self,
          interaction: discord.Interaction,
          action: str,
          word: str = None,
          points: int = None,
     ):
          # Check if the user has permission to use this command
          if not await self.has_permission(interaction):
               await interaction.response.send_message(
                    "You do not have permission to use this command.", ephemeral=True
               )
               return
          """
          Manage filtered words for the guild.

          Parameters:
          - action: add, remove, update, view
          - word: the word to manage
          - points: the point value to associate (required for add/update)
          """
          self.reconnect_database()

          guild_id = interaction.guild_id

          if action not in ["add", "remove", "update", "view"]:
               await interaction.response.send_message(
                    "Invalid action. Use `add`, `remove`, `update`, or `view`.",
                    ephemeral=True,
               )
               return

          if action in ["add", "remove", "update"] and not word:
               await interaction.response.send_message(
                    "You must specify a word for this action.", ephemeral=True
               )
               return

          # Fetch the current chat words
          chat_words = self.fetch_chat_words(guild_id)

          if action == "view":
               if not chat_words:
                    await interaction.response.send_message(
                         "No filtered words are currently set.", ephemeral=True
                    )
               else:
                    formatted_words = "\n".join(
                         [f"- **{w}**: {p} points" for w, p in chat_words.items()]
                    )
                    await interaction.response.send_message(
                         f"**Filtered Words:**\n{formatted_words}", ephemeral=True
                    )

          elif action == "add":
               if word in chat_words:
                    await interaction.response.send_message(
                         f"The word `{word}` is already in the filter list.",
                         ephemeral=True,
                    )
                    return
               if points is None:
                    await interaction.response.send_message(
                         "You must provide a point value to add a new word.",
                         ephemeral=True,
                    )
                    return
               chat_words[word] = points
               self.update_chat_words(guild_id, chat_words)
               await interaction.response.send_message(
                    f"Added `{word}` with {points} points to the filter list.",
                    ephemeral=True,
               )

          elif action == "remove":
               if word not in chat_words:
                    await interaction.response.send_message(
                         f"The word `{word}` is not in the filter list.", ephemeral=True
                    )
                    return
               del chat_words[word]
               self.update_chat_words(guild_id, chat_words)
               await interaction.response.send_message(
                    f"Removed `{word}` from the filter list.", ephemeral=True,
               )

          elif action == "update":
               if word not in chat_words:
                    await interaction.response.send_message(
                         f"The word `{word}` is not in the filter list. Use `add` to add it first.",
                         ephemeral=True,
                    )
                    return
               if points is None:
                    await interaction.response.send_message(
                         "You must provide a point value to update a word.",
                         ephemeral=True,
                    )
                    return
               chat_words[word] = points
               self.update_chat_words(guild_id, chat_words)
               await interaction.response.send_message(
                    f"Updated `{word}` to {points} points in the filter list.",
                    ephemeral=True,
               )

     @commands.Cog.listener()
     async def on_message(self, message):
          """Listener to detect filtered words in chat messages."""
          if message.author.bot:
               return

          self.reconnect_database()
          guild_id = message.guild.id
          chat_words = self.fetch_chat_words(guild_id)

          detected_words = {
               word: points for word, points in chat_words.items() if word in message.content
          }

          if detected_words:
               total_points = sum(detected_words.values())
               for word, points in detected_words.items():
                    self.update_user_points(guild_id, message.author.id, word, points)

               await message.channel.send(
                    f"{message.author.mention}, you used prohibited words. {total_points} points have been added to your record."
               )


async def setup(bot):
     await bot.add_cog(WordFilter(bot))
