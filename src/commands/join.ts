import {ChatInputCommandInteraction, GuildMember, VoiceChannel} from 'discord.js';
import {SlashCommandBuilder} from '@discordjs/builders';
import {inject, injectable} from 'inversify';
import PlayerManager from '../managers/player.js';
import {TYPES} from '../types.js';
import Command from './index.js';
import {getMemberVoiceChannel, getMostPopularVoiceChannel} from '../utils/channels.js';

@injectable()
export default class Join implements Command {
  public readonly slashCommand = new SlashCommandBuilder()
    .setName('join')
    .setDescription('join your current voice channel');

  public requiresVC = true;

  private readonly playerManager: PlayerManager;

  constructor(@inject(TYPES.Managers.Player) playerManager: PlayerManager) {
    this.playerManager = playerManager;
  }

  public async execute(interaction: ChatInputCommandInteraction): Promise<void> {
    const [targetVoiceChannel] =
      getMemberVoiceChannel(interaction.member as GuildMember) ??
      getMostPopularVoiceChannel(interaction.guild!);

    const player = this.playerManager.get(interaction.guild!.id);

    await player.connect(targetVoiceChannel as VoiceChannel);

    await interaction.reply(`Joined <#${targetVoiceChannel.id}>`);

    console.log("Joined! Player status: ", player.status)
  }
}