import asyncio
import discord
import config
from discord import app_commands
import json
import os
from discord.ext import commands

intents = discord.Intents.all()
client = discord.Client(intents=intents)
tree = app_commands.CommandTree(client)
bot = commands.Bot(command_prefix="/", intents=intents)

PATH_SERVER_VERSION = "./src/server_version.txt"
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
    "current_version_key": None,  # ユーザーに聞いたバージョンキーを保持
}


# bot起動時に発火
@client.event
async def on_ready():
    print(f"✅ ログインしました: {bot.user}")
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
        version_key = state["current_version_key"]
        if not version_key:
            await message.channel.send("❌ バージョンキーが設定されていません。")
            state["write_json"] = False
            return

        with open(path_json, "r") as f_r:
            all_reactions = json.load(f_r)

        # 初期化（まだこのバージョンキーがない場合）
        if version_key not in all_reactions:
            all_reactions[version_key] = {
                "Soprano_attend": "",
                "Alto_attend": "",
                "Tenor_attend": "",
                "Bass_attend": "",
                "Soprano_absent": "",
                "Alto_absent": "",
                "Tenor_absent": "",
                "Bass_absent": "",
                "delay": "",
                "off_stage": "",
            }

        reaction_keys = list(all_reactions[version_key])

        if state["reaction_num"] + 2 > len(reaction_keys):
            state["write_json"] = False
            state["current_version_key"] = None
            await message.channel.send("✅ 出欠席リアクションIDの設定を完了しました。")
        else:
            await message.channel.send(reaction_keys[state["reaction_num"] + 1])

        if state["reaction_num"] < len(reaction_keys):
            key = reaction_keys[state["reaction_num"]]
            all_reactions[version_key][key] = message.content
            state["reaction_num"] += 1

            with open(path_json, "w") as f_w:
                json.dump(all_reactions, f_w, indent=4, ensure_ascii=False)

    # TXTファイルへのアプリID書き込み
    if state["write_txt"]:
        with open(path_txt, "w") as f_w:
            f_w.write(message.content)
        state["write_txt"] = False
        await message.channel.send("アプリIDの設定が完了しました")


@bot.tree.command(
    name="update_reactions-id",
    description="出欠席リアクションIDを設定します、まずバージョンキー（使用サーバの年度）を入力してください",
)
async def start_update_reaction(interaction: discord.Interaction):
    await interaction.response.send_message(
        "📝 この設定の対象となるバージョンキー（例: `2025`）を入力してください。"
    )

    def check_msg(m):
        return m.author == interaction.user and m.channel == interaction.channel

    try:
        msg = await client.wait_for("message", check=check_msg, timeout=60.0)
        version_key = msg.content.strip()

        if not version_key.isdigit():
            await interaction.followup.send(
                "⚠️ 無効なキーです。数値（例: `2025`）を入力してください。"
            )
            return

        # JSONの読み込み
        with open(path_json, "r") as f:
            all_reactions = json.load(f)

        # 既存バージョンが存在する場合、上書き確認
        if version_key in all_reactions:
            warning_msg = await interaction.followup.send(
                f"⚠️ バージョンキー `{version_key}` はすでに存在します。上書きしてもよろしいですか？",
            )
            await warning_msg.add_reaction("✅")
            await warning_msg.add_reaction("❌")

            def check_reaction(reaction, user):
                return (
                    user == interaction.user
                    and reaction.message.id == warning_msg.id
                    and str(reaction.emoji) in ["✅", "❌"]
                )

            try:
                reaction, _ = await client.wait_for(
                    "reaction_add", check=check_reaction, timeout=30.0
                )

                if str(reaction.emoji) == "❌":
                    await interaction.followup.send("❌ 操作をキャンセルしました。")
                    return
                # ✅ の場合 → 続行

            except asyncio.TimeoutError:
                await interaction.followup.send(
                    "⏰ 時間切れです。操作をキャンセルしました。"
                )
                return

        # 書き込み処理を続行
        client.state["write_json"] = True
        client.state["reaction_num"] = 0
        client.state["current_version_key"] = version_key

        await interaction.followup.send(
            f"✅ バージョンキー `{version_key}` に対してリアクションIDの設定を開始します。\nまず `Soprano_attend` に対応するリアクションIDを送信してください。"
        )

    except asyncio.TimeoutError:
        await interaction.followup.send(
            "⏰ 時間切れです。もう一度 `/update_reactions-id` を実行してください。"
        )


# スラッシュコマンド：BotアプリID設定
@bot.tree.command(name="update_bot-id", description="botのアプリIDを設定します")
async def finish_update_reaction(interaction: discord.Interaction):
    client.state["write_txt"] = True
    await interaction.response.send_message(
        "botのアプリIDを設定します。アプリIDを返信してください。"
    )


@bot.tree.command(
    name="set_attender-server-version",
    description="サーバのバージョンを記録します",
)
async def set_server_version(interaction: discord.Interaction):
    await interaction.response.send_message(
        "使用するサーバの年度を数字のみでこのチャンネルで送ってください。"
    )

    def check(m):
        return m.author == interaction.user and m.channel == interaction.channel

    try:
        msg = await bot.wait_for(
            "message", check=check, timeout=60.0
        )  # 60秒のタイムアウト
    except asyncio.TimeoutError:
        await interaction.followup.send(
            "⚠️ 時間切れです。もう一度 `/set_server_version` を実行してください。"
        )
        return

    if not msg.content.isdigit():
        await interaction.followup.send(
            "⚠️ 入力は数字のみでお願いします。もう一度 `/set_server_version` を実行してください。"
        )
        return

    file_path = os.path.join(os.path.dirname(__file__), PATH_SERVER_VERSION)
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(f"{msg.content}\n")

    await interaction.followup.send("✅ サーバのバージョンを書き込みました。")


# Bot起動
client.run(config.DISCORD_TOKEN)
