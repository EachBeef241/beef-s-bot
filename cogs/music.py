import discord
import asyncio
import traceback
import re
import math
from discord import app_commands
from discord.ext import commands
from youtube_dl import YoutubeDL

URL_REG = re.compile(r'https?://(?:www\.)?.+')
YOUTUBE_VIDEO_REG = re.compile(r"(https?://)?(www\.)?youtube\.(com|nl)/watch\?v=([-\w]+)")

class TutorialButton(discord.ui.View):
    def __init__(self):
        super().__init__()
        self.value = None
        self.timeout = 600

        botaourl = discord.ui.Button(label="ticking away", url="https://www.youtube.com/watch?v=bu5wuKGriMw")
        self.add_item(botaourl)

class Music(commands.Cog):
    def __init__(self, client):
        self.client = client

        # all the music related stuff
        self.is_playing = False
        self.event = asyncio.Event()

        # 2D array containing [song, channel]
        self.music_queue = []
        self.YDL_OPTIONS = {
            'format': 'bestaudio/best',
            'restrictfilenames': True,
            'noplaylist': True,
            'nocheckcertificate': True,
            'ignoreerrors': False,
            'logtostderr': False,
            'quiet': True,
            'no_warnings': True,
            'extract_flat': True
        }
        self.FFMPEG_OPTIONS = {'before_options': '-nostdin -reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5', 'options': '-vn'}

        self.vc = None

    async def search_yt(self, item):
        with YoutubeDL(self.YDL_OPTIONS) as ydl:
            try:
                if (yt_url := YOUTUBE_VIDEO_REG.match(item)):
                    item = yt_url.group()
                elif not URL_REG.match(item):
                    item = f"ytsearch:{item}"
                info = ydl.extract_info(item, download=False)
            except Exception:
                traceback.print_exc()
                return False

        try:
            entries = info["entries"]
        except KeyError:
            entries = [info]

        if info["extractor_key"] == "YoutubeSearch":
            entries = entries[:1]

        tracks = []

        for t in entries:
            duration = t.get('duration', 0)
            minutes = math.floor(duration / 60)
            seconds = duration % 60
            duration_formatted = f"{minutes}m:{seconds}s"
            tracks.append({'source': f'https://www.youtube.com/watch?v={t["id"]}', 'title': t['title'], 'duration': duration_formatted})

        return tracks

    async def play_music(self):
        self.event.clear()

        if len(self.music_queue) > 0:
            self.is_playing = True
            m_url = self.music_queue[0][0]['source']

            with YoutubeDL(self.YDL_OPTIONS) as ydl:
                try:
                    info = ydl.extract_info(m_url, download=False)
                    m_url = info['formats'][0]['url']
                except Exception:
                    return False

            if self.vc is None or not self.vc.is_connected():
                self.vc = await self.music_queue[0][1].connect()
            else:
                await self.vc.move_to(self.music_queue[0][1])

            self.music_queue.pop(0)

            self.vc.play(discord.FFmpegPCMAudio(m_url, **self.FFMPEG_OPTIONS), after=lambda l: self.client.loop.call_soon_threadsafe(self.event.set))
            await self.event.wait()
            await self.play_music()
        else:
            self.is_playing = False
            self.music_queue.clear()
            await self.vc.disconnect()

    @app_commands.command(name="ajuda", description="Mostre um comando de ajuda.")
    async def help(self, interaction: discord.Interaction):
        try:
            await interaction.response.defer(thinking=True)
        except discord.errors.NotFound:
            pass

        helptxt = "`/ajuda` - Veja esse guia!\n`/play` - Toque uma música do YouTube!\n`/fila` - Veja a fila de músicas na Playlist\n`/pular` - Pule para a próxima música da fila\n`/sair` - faça o bot sair da call"
        embedhelp = discord.Embed(
            colour=1646116,
            title=f'Comandos do {self.client.user.name}',
            description=helptxt + '\n[CBOT por @eachbeef'
        )
        try:
            embedhelp.set_thumbnail(url=self.client.user.avatar.url)
        except:
            pass
        try:
            await interaction.followup.send(embed=embedhelp, view=TutorialButton())
        except discord.errors.NotFound:
            pass

    @app_commands.command(name="play", description="Toca uma música do YouTube.")
    @app_commands.describe(busca="Digite o nome da música no YouTube")
    async def play(self, interaction: discord.Interaction, busca: str):
        try:
            await interaction.response.defer(thinking=True)
        except discord.errors.NotFound:
            pass

        query = busca

        try:
            voice_channel = interaction.user.voice.channel
        except AttributeError:
            embedvc = discord.Embed(
                colour=1646116,
                description='Para tocar uma música, primeiro se conecte a um canal de voz.'
            )
            await interaction.followup.send(embed=embedvc)
            return

        songs = await self.search_yt(query)
        if not songs:
            embedvc = discord.Embed(
                colour=12255232,
                description='Algo deu errado! Tente mudar ou configurar a playlist/vídeo ou escrever o nome dele novamente!'
            )
            await interaction.followup.send(embed=embedvc)
        else:
            embedvc = discord.Embed(
                colour=32768,
                description="Você adicionou a(s) música(s) à fila!"
            )
            for song in songs:
                embedvc.add_field(name=song['title'], value=f"**Duração:** {song['duration']}", inline=False)
                self.music_queue.append([song, voice_channel])
            await interaction.followup.send(embed=embedvc, view=TutorialButton())

            if not self.is_playing:
                await self.play_music()

    @app_commands.command(name="fila", description="Mostra as atuais músicas da fila.")
    async def q(self, interaction: discord.Interaction):
        try:
            await interaction.response.defer(thinking=True)
        except discord.errors.NotFound:
            pass

        retval = ""
        MAX_SONGS = 10
        for i in range(0, min(len(self.music_queue), MAX_SONGS)):
            retval += f'**{i + 1} - **' + self.music_queue[i][0]['title'] + "\n"

        if retval != "":
            embedvc = discord.Embed(
                colour=12255232,
                description=retval
            )
            try:
                await interaction.followup.send(embed=embedvc)
            except discord.errors.NotFound:
                pass
        else:
            embedvc = discord.Embed(
                colour=1646116,
                description='Não existem músicas na fila no momento.'
            )
            try:
                await interaction.followup.send(embed=embedvc)
            except discord.errors.NotFound:
                pass

    @app_commands.command(name="pular", description="Pula a atual música que está tocando.")
    async def skip(self, interaction: discord.Interaction):
        if self.vc and self.vc.is_playing():
            self.vc.stop()
            embedvc = discord.Embed(
                colour=1646116,
                description="Você pulou a música."
            )
            await interaction.followup.send(embed=embedvc)

    @app_commands.command(name="sair", description="Faça o bot sair da call")
    async def leave(self, interaction: discord.Interaction):
        try:
            await interaction.response.defer(thinking=True)
        except discord.errors.NotFound:
            pass

        embedvc = discord.Embed(colour=12255232)

        if not interaction.guild.voice_client:
            embedvc.description = "Não estou conectado em nenhum canal de voz."
            try:
                await interaction.followup.send(embed=embedvc)
            except discord.errors.NotFound:
                pass
            return

        if not interaction.user.voice or interaction.user.voice.channel != interaction.guild.voice_client.channel:
            embedvc.description = "Você precisa estar no canal de voz atual para se utilizar desse comando."
            try:
                await interaction.followup.send(embed=embedvc)
            except discord.errors.NotFound:
                pass
            return

        if any(m for m in interaction.guild.voice_client.channel.members if not m.bot and m.guild_permissions.manage_channels) and not interaction.user.guild_permissions.manage_channels:
            embedvc.description = "No momento você não tem permissão para usar esse comando."
            try:
                await interaction.followup.send(embed=embedvc)
            except discord.errors.NotFound:
                pass
            return

        self.is_playing = False
        self.music_queue.clear()
        await interaction.guild.voice_client.disconnect()

        embedvc.colour = 1646116
        embedvc.description = "Você parou o player."
        try:
            await interaction.followup.send(embed=embedvc)
        except discord.errors.NotFound:
            pass

async def setup(client):
    await client.add_cog(Music(client))
