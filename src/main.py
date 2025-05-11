import discord
import config
from discord import app_commands
import json
import os

intents = discord.Intents.all()
client = discord.Client(intents=intents)
tree = app_commands.CommandTree(client)

# dockercontainer用
path_json = "/shared_data/reactions.json"
path_txt = "/shared_data/id.txt"
# local用
# path_json = "./src/reactions.json"
# path_txt = "./src/id.txt"

# 状態をclientに保存
client.state = {
    "write_json": False,
    "write_txt": False,
    "reaction_num": 0,
}


# ファイルの初期化（存在しない場合に作成）
def initialize_files():
    if not os.path.exists(path_json):
        with open(path_json, "w") as f:
            json.dump(
                {
                    "Soprano_attend": "",
                    "Alto_attend": "",
                    "Tenor_attend": "",
                    "Bass_attend": "",
                },
                f,
                indent=4,
            )

    if not os.path.exists(path_txt):
        with open(path_txt, "w") as f:
            f.write("")


# bot起動時に発火
@client.event
async def on_ready():
    print("bot is online!")
    initialize_files()
    await client.change_presence(activity=discord.Game(name="出欠確認中"))
    await tree.sync()


# メッセージの検知
@client.event
async def on_message(message):
    if message.author == client.user:
        return

    state = client.state

    # ユーザーからのメンションを受け取った場合
    if client.user in message.mentions:
        with open(path_json, "r") as f_json:
            reaction_dict = json.load(f_json)
        reaction_list = list(reaction_dict)

        with open(path_txt, "r") as f_txt:
            len_id = len(f_txt.read())

        # メッセージの残りをスレッド名として利用
        thread_name = message.content[len_id + 4 :]
        thread = await message.channel.create_thread(
            name=thread_name, message=message, type=discord.ChannelType.public_thread
        )
        await thread.send("遅刻・欠席・その他連絡はこちらから！")

        # リアクションを付与
        for emoji in reaction_list:
            emoji_id = f"<:{emoji}:{reaction_dict[emoji]}>"
            try:
                await message.add_reaction(emoji_id)
            except discord.HTTPException as e:
                await message.channel.send(
                    f"リアクション追加に失敗しました: {emoji_id}"
                )

    # JSONファイルへのリアクションID書き込み
    if state["write_json"]:
        with open(path_json, "r") as f_r:
            reaction_dict = json.load(f_r)
        reaction_list = list(reaction_dict)

        if state["reaction_num"] + 2 > len(reaction_list):
            state["write_json"] = False
            await message.channel.send(
                "出欠席リアクションの設定を終了しました。@メンションをして正しく設定されているかを確認してください。"
            )
        else:
            await message.channel.send(reaction_list[state["reaction_num"] + 1])

        if state["reaction_num"] < len(reaction_list):
            dict_key = reaction_list[state["reaction_num"]]
            reaction_dict[dict_key] = message.content
            state["reaction_num"] += 1
            with open(path_json, "w") as f_w:
                json.dump(reaction_dict, f_w, indent=4)

    # TXTファイルへのアプリID書き込み
    if state["write_txt"]:
        with open(path_txt, "w") as f_w:
            f_w.write(message.content)
        state["write_txt"] = False
        await message.channel.send("アプリIDの設定が完了しました")


# スラッシュコマンド：リアクションID設定開始
@tree.command(
    name="update_reactions-id", description="出欠席リアクションIDを設定します"
)
async def start_update_reaction(interaction: discord.Interaction):
    client.state["write_json"] = True
    client.state["reaction_num"] = 0
    await interaction.response.send_message(
        "出欠席リアクションのIDを設定します。リアクションに対応するものを返信してください。\nSoprano_attend"
    )


# スラッシュコマンド：BotアプリID設定
@tree.command(name="update_bot-id", description="botのアプリIDを設定します")
async def finish_update_reaction(interaction: discord.Interaction):
    client.state["write_txt"] = True
    await interaction.response.send_message(
        "botのアプリIDを設定します。アプリIDを返信してください。"
    )


# Bot起動
client.run(config.DISCORD_TOKEN)
