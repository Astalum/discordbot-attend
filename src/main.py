import discord
import config
from discord import app_commands

# import re
import json

intents = discord.Intents.all()
client = discord.Client(intents=intents)
tree = app_commands.CommandTree(client)

# dockercontainer用
path_json = "/app/src/reactions.json"
path_txt = "/app/src/id.txt"
# local用
# path_json = "./reactions.json"
# path_txt = "./id.txt"
write_json = False
write_txt = False


# bot起動時に発火
@client.event
async def on_ready():
    print("bot is online!")
    global write_json
    global write_txt
    write_json = False
    write_txt = False
    await client.change_presence(activity=discord.Game)
    # スラッシュコマンドを同期
    await tree.sync()


# メッセージの検知
@client.event
async def on_message(message):
    global write_json
    global write_txt
    global reaction_num
    global path_json
    # 自身が送信したメッセージには反応しない
    if message.author == client.user:
        return

    # ユーザーからのメンションを受け取った場合、そのメッセージにリアクションをつけ、スレッドを作る
    if client.user in message.mentions:
        with open(path_json, "r") as f_json:
            reaction_dict = json.load(f_json)
        reaction_list = list(reaction_dict)
        with open(path_txt, "r") as f_txt:
            len_id = len(f_txt.read())
            # print(len_id)
        len_id += 4
        thread_name = message.content[len_id:]
        channel = message.channel
        # print(thread_name)
        thread = await channel.create_thread(
            name=thread_name, message=message, type=discord.ChannelType.public_thread
        )
        await thread.send("遅刻・欠席・その他連絡はこちらから！")
        for emoji in reaction_list:
            emoji_id = "<:" + emoji + ":" + reaction_dict[emoji] + ">"
            await message.add_reaction(emoji_id)
    # JSONファイルへの書き込み
    if write_json == True:
        with open(path_json, "r") as f_r:
            reaction_dict = json.load(f_r)
        reaction_list = list(reaction_dict)
        # print(reaction_dict)
        if reaction_num + 2 > len(reaction_list):
            write_json = False
            await message.channel.send(
                "出欠席リアクションの設定を終了しました。@メンションをして正しく設定されているかを確認してください。"
            )
        else:
            await message.channel.send(reaction_list[reaction_num + 1])
        if reaction_num <= len(reaction_list):
            dict_key = reaction_list[reaction_num]
            reaction_dict[dict_key] = message.content
            reaction_num += 1
            with open(path_json, "w") as f_w:
                json.dump(reaction_dict, f_w, indent=4)
        # print(reaction_dict)
    # TXTファイルへの書き込み
    if write_txt == True:
        with open(path_txt, "w") as f_w:
            f_w.write(message.content)
        write_txt = False
        await message.channel.send("アプリIDの設定が完了しました")


@tree.command(
    name="update_reactions-id", description="出欠席リアクションIDを設定します"
)
async def start_update_reaction(interaction: discord.Interaction):
    global write_json
    global reaction_num
    write_json = True
    reaction_num = 0
    await interaction.response.send_message(
        "出欠席リアクションのIDを設定します。リアクションに対応するものを返信してください。\nSoprano_attend"
    )


@tree.command(name="update_bot-id", description="botのアプリIDを設定します")
async def finish_update_reaction(interaction: discord.Interaction):
    global write_txt
    write_txt = True
    await interaction.response.send_message(
        "botのアプリIDを設定します。アプリIDを返信してください。"
    )


# Bot起動
client.run(config.DISCORD_TOKEN)
