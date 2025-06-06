import {ChatInputCommandInteraction, TextBasedChannel} from 'discord.js';
import {TYPES, MaybeApiMockInteraction} from '../types.js';
import {inject, injectable} from 'inversify';
import PlayerManager from '../managers/player.js';
import Command from './index.js';
import {SlashCommandBuilder} from '@discordjs/builders';
import {buildPlayingMessageEmbed} from '../utils/build-embed.js';

@injectable()
export default class NowPlaying implements Command {
  public readonly slashCommand = new SlashCommandBuilder()
    .setName('now-playing')
    .setDescription('shows the currently played song');

  private readonly playerManager: PlayerManager;

  constructor(@inject(TYPES.Managers.Player) playerManager: PlayerManager) {
    this.playerManager = playerManager;
  }

  public async execute(interaction: MaybeApiMockInteraction): Promise<void> {
    const player = this.playerManager.get(interaction.guild!.id);

    if (!player.getCurrent()) {
      throw new Error('nothing is currently playing');
    }

    if (interaction.__isApiMock) {
      await (interaction.channel as TextBasedChannel).send({
        embeds: [buildPlayingMessageEmbed(player)],
      });
    } else {
      await interaction.reply({
        embeds: [buildPlayingMessageEmbed(player)],
      });
    }
  }
}
