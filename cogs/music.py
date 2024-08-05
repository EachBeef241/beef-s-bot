import discord
import asyncio
import traceback
import re
import math
from discord import app_commands
from discord.ext import commands
from yt_dlp import YoutubeDL

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

        # Armazenar as filas de músicas e conexões por servidor
        self.music_queues = {}
        self.voice_clients = {}
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

    async def play_music(self, guild_id):
        if guild_id not in self.music_queues or guild_id not in self.voice_clients:
            return

        music_queue = self.music_queues[guild_id]
        vc = self.voice_clients[guild_id]

        if len(music_queue) > 0:
            self.music_queues[guild_id] = music_queue
            m_url = music_queue[0][0]['source']

            with YoutubeDL(self.YDL_OPTIONS) as ydl:
                try:
                    info = ydl.extract_info(m_url, download=False)
                    formats = info.get('formats', [])

                    # Encontre o formato de áudio com maior qualidade
                    m_url = next((f['url'] for f in formats if f.get('acodec') and f['acodec'] != 'none'), None)

                    if not m_url:
                        # Se nenhum formato com 'acodec' encontrado, busque um URL de áudio
                        m_url = next((f['url'] for f in formats if f['url']), None)

                    if not m_url:
                        print("Nenhuma URL de áudio encontrada.")
                        return False

                    print(f"URL da música: {m_url}")

                except Exception as e:
                    print(f"Erro ao obter URL da música: {e}")
                    traceback.print_exc()
                    return False

            try:
                # Conecte ao canal de voz se não estiver conectado
                if vc is None or not vc.is_connected():
                    voice_channel = music_queue[0][1]
                    self.voice_clients[guild_id] = await voice_channel.connect()
                    vc = self.voice_clients[guild_id]
                    print("Conectado ao canal de voz.")
                else:
                    await vc.move_to(music_queue[0][1])
                    print("Movido para o canal de voz.")

                music_queue.pop(0)

                vc.play(discord.FFmpegPCMAudio(m_url, **self.FFMPEG_OPTIONS), after=lambda l: asyncio.run_coroutine_threadsafe(self.play_music(guild_id), self.client.loop))
                print("Música está tocando.")

                # Verifique se a música começou a tocar
                await asyncio.sleep(10)  # Atraso de 10 segundos, ajuste se necessário

                if vc.is_playing():
                    print("Música está tocando corretamente.")
                else:
                    print("A música não começou a tocar.")

            except Exception as e:
                print(f"Erro ao conectar ou reproduzir música: {e}")
                traceback.print_exc()
                self.music_queues[guild_id].clear()
                self.voice_clients.pop(guild_id, None)
                if vc:
                    await vc.disconnect()

        else:
            if guild_id in self.voice_clients:
                vc = self.voice_clients.pop(guild_id, None)
                if vc:
                    await vc.disconnect()
            self.music_queues[guild_id].clear()

    @app_commands.command(name="ajuda", description="Mostre um comando de ajuda.")
    async def help(self, interaction: discord.Interaction):
        try:
            await interaction.response.defer(thinking=True)
        except discord.errors.NotFound:
            pass

        helptxt = "`/ajuda` - Veja esse guia!\n`/play` - Toque uma música do YouTube!\n`/fila` - Veja a fila de músicas na Playlist\n`/pular` - Pule para a próxima música da fila\n`/sair` - Faça o bot sair da call\n`/pause` - Pause a música atual\n`/resume` - Retome a música pausada"
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
        guild_id = interaction.guild.id

        try:
            voice_channel = interaction.user.voice.channel
        except AttributeError:
            embedvc = discord.Embed(
                colour=1646116,
                description='Para tocar uma música, primeiro se conecte a um canal de voz.'
            )
            await interaction.followup.send(embed=embedvc)
            return

        if guild_id not in self.music_queues:
            self.music_queues[guild_id] = []

        if guild_id not in self.voice_clients:
            self.voice_clients[guild_id] = None

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
                self.music_queues[guild_id].append([song, voice_channel])
            await interaction.followup.send(embed=embedvc, view=TutorialButton())

            if not self.voice_clients[guild_id] or not self.voice_clients[guild_id].is_playing():
                await self.play_music(guild_id)

    @app_commands.command(name="fila", description="Mostra as atuais músicas da fila.")
    async def q(self, interaction: discord.Interaction):
        try:
            await interaction.response.defer(thinking=True)
        except discord.errors.NotFound:
            pass

        retval = ""
        MAX_SONGS = 10
        guild_id = interaction.guild.id

        for i in range(0, min(len(self.music_queues.get(guild_id, [])), MAX_SONGS)):
            retval += f'**{i + 1}**: ' + self.music_queues[guild_id][i][0]['title'] + "\n"

        if len(self.music_queues.get(guild_id, [])) > MAX_SONGS:
            retval += f"... e mais {len(self.music_queues[guild_id]) - MAX_SONGS} músicas na fila!"

        if retval != "":
            embedvc = discord.Embed(
                colour=1646116,
                description=retval
            )
            await interaction.followup.send(embed=embedvc)
        else:
            embedvc = discord.Embed(
                colour=12255232,
                description='Nenhuma música na fila no momento.'
            )
            try:
                await interaction.followup.send(embed=embedvc)
            except discord.errors.NotFound:
                pass

    @app_commands.command(name="pular", description="Pula a atual música que está tocando.")
    async def skip(self, interaction: discord.Interaction):
        guild_id = interaction.guild.id
        if guild_id in self.voice_clients and self.voice_clients[guild_id] and self.voice_clients[guild_id].is_playing():
            self.voice_clients[guild_id].stop()
            embedvc = discord.Embed(
                colour=1646116,
                description="Você pulou a música."
            )
            await interaction.followup.send(embed=embedvc)
            await self.play_music(guild_id)

    @app_commands.command(name="sair", description="Faça o bot sair da call")
    async def leave(self, interaction: discord.Interaction):
        try:
            await interaction.response.defer(thinking=True)
        except discord.errors.NotFound:
            pass

        embedvc = discord.Embed(colour=12255232)
        guild_id = interaction.guild.id

        if guild_id not in self.voice_clients or not self.voice_clients[guild_id]:
            embedvc.description = "Não estou conectado em nenhum canal de voz."
            try:
                await interaction.followup.send(embed=embedvc)
            except discord.errors.NotFound:
                pass
            return

        self.music_queues.pop(guild_id, None)
        if guild_id in self.voice_clients:
            vc = self.voice_clients.pop(guild_id, None)
            if vc:
                await vc.disconnect()

        embedvc.colour = 1646116
        embedvc.description = "Você parou o player."
        try:
            await interaction.followup.send(embed=embedvc)
        except discord.errors.NotFound:
            pass

    @app_commands.command(name="pause", description="Pause a música atual.")
    async def pause(self, interaction: discord.Interaction):
        try:
            await interaction.response.defer(thinking=True)
        except discord.errors.NotFound:
            pass

        guild_id = interaction.guild.id
        if guild_id in self.voice_clients and self.voice_clients[guild_id] and self.voice_clients[guild_id].is_playing():
            self.voice_clients[guild_id].pause()
            embedvc = discord.Embed(
                colour=1646116,
                description="Você pausou a música."
            )
            await interaction.followup.send(embed=embedvc)

    @app_commands.command(name="resume", description="Retome a música pausada.")
    async def resume(self, interaction: discord.Interaction):
        try:
            await interaction.response.defer(thinking=True)
        except discord.errors.NotFound:
            pass

        guild_id = interaction.guild.id
        if guild_id in self.voice_clients and self.voice_clients[guild_id] and self.voice_clients[guild_id].is_paused():
            self.voice_clients[guild_id].resume()
            embedvc = discord.Embed(
                colour=1646116,
                description="Você retomou a música."
            )
            await interaction.followup.send(embed=embedvc)

async def setup(client):
    await client.add_cog(Music(client))
