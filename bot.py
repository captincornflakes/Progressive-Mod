import io
import shutil
import zipfile
import discord
from discord.ext import commands
import os
import json
import tracemalloc
import logging
import os
import mysql.connector
import requests

#pip install mysql-connector-python
#pip install discord.py
#pip install requests

handler = logging.FileHandler(filename='discord.log', encoding='utf-8', mode='w')
logging.basicConfig(level=logging.INFO, handlers=[handler])

def download_repo_as_zip(repo_url, temp_folder):
    # Remove the need for a token, use a public URL for downloading the zip file
    zip_url = f"{repo_url}/archive/refs/heads/main.zip"
    print(f"Downloading repository from {zip_url}...")
    
    try:
        response = requests.get(zip_url)
        response.raise_for_status()  # Raise an error for HTTP errors
    except requests.exceptions.RequestException as e:
        print(f"Failed to download repository: {e}")
        raise
    
    print(f"Extracting ZIP file to {temp_folder}...")
    
    try:
        with zipfile.ZipFile(io.BytesIO(response.content)) as zip_file:
            zip_file.extractall(temp_folder)
    except zipfile.BadZipFile as e:
        print(f"Failed to extract ZIP file: {e}")
        raise
    
    print(f"Repository extracted to {temp_folder}.")

def extract_functions_folder(temp_folder, target_folder):
    repo_folder = os.path.join(temp_folder, config['repo_temp'])
    functions_folder = os.path.join(repo_folder, "functions")
    if not os.path.exists(functions_folder):
        raise FileNotFoundError(f"'functions' folder not found in {repo_folder}.")
    if os.path.exists(target_folder):
        print(f"Removing existing target folder: {target_folder}")
        shutil.rmtree(target_folder)
    print(f"Copying 'functions' folder to {target_folder}...")
    os.makedirs(target_folder, exist_ok=True)
    for item in os.listdir(functions_folder):
        source = os.path.join(functions_folder, item)
        destination = os.path.join(target_folder, item)
        if os.path.isdir(source):
            shutil.copytree(source, destination, dirs_exist_ok=True)
        else:
            shutil.copy2(source, destination)

def load_github():
    if config['use_Git']:
        print("Pulling repository from GitHub...")
        repo_url = config['repo_url']
        temp_folder = "repository_contents"
        target_folder = "functions"
        try:
            download_repo_as_zip(repo_url, temp_folder)  # No need for token
            extract_functions_folder(temp_folder, target_folder)
        finally:
            if os.path.exists(temp_folder):
                print(f"Cleaning up temporary folder: {temp_folder}")
                shutil.rmtree(temp_folder)

def load_config():
    config_file = "datastores/config.json"
    config = None
    try:
        with open(config_file, 'r') as f:
            config = json.load(f)
            print(f"Loaded configuration from {config_file}.")
    except FileNotFoundError:
        print(f"{config_file} not found...")
    return config
config = load_config()
load_github()

# Define the intents you want your bot to have
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.guilds = True

# Prefix and bot initialization
PREFIX = "!"

# Load application_id as an integer
application_id = int(config['application_id'])
bot = commands.AutoShardedBot(command_prefix=PREFIX, intents=intents, application_id=application_id, help_command=None)

# Set up the database connection
db_config = config['database']
db_connection = mysql.connector.connect(
    host=db_config['host'],
    user=db_config['user'],
    password=db_config['password'],
    database=db_config['database'],
    autocommit=True,
    connection_timeout=6000
)
# Store the connection in the bot instance
bot.db_connection = db_connection

# Start memory tracking
tracemalloc.start()

# Function to load all Python files from a directory as extensions
async def load_extensions_from_folder(folder):
    for filename in os.listdir(folder):
        if filename.endswith('.py') and filename != '__init__.py':
            module_name = filename[:-3]
            module_path = f'{folder}.{module_name}'
            try:
                await bot.load_extension(module_path)
                print(f'Loaded extension: {module_path}')
            except Exception as e:
                print(f'Failed to load extension {module_path}. Reason: {e}')

@bot.event
async def on_ready():
    activity = discord.Activity(type=discord.ActivityType.playing, name=config['status'])
    await bot.change_presence(status=discord.Status.online, activity=activity)
    print(f'Logged in as {bot.user.name} ({bot.user.id})')
    print(f"Shard ID: {bot.shard_id}")
    print(f"Total Shards: {bot.shard_count}")
    
    for shard_id, latency in bot.latencies:
        print(f"Shard ID: {shard_id} | Latency: {latency*1000:.2f}ms")

# Event: Sync commands when bot joins a new guild
@bot.event
async def on_guild_join(guild):
    await bot.tree.sync(guild=guild)

# Setup hook to load extensions
async def setup_hook():
    await load_extensions_from_folder('functions')
    await bot.tree.sync()

# Assign setup_hook to the bot
bot.setup_hook = setup_hook

# Run the bot with your token
if __name__ == '__main__':
    token = config['token']
    bot.run(token, log_handler=handler, log_level=logging.INFO)
