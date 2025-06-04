import express from 'express';
import {Client, Collection, User, GatewayIntentBits, ChatInputCommandInteraction} from 'discord.js';
import {inject, injectable} from 'inversify';
import ora from 'ora';
import {TYPES} from './types.js';
import container from './inversify.config.js';
import Command from './commands/index.js';
import debug from './utils/debug.js';
import handleGuildCreate from './events/guild-create.js';
import handleVoiceStateUpdate from './events/voice-state-update.js';
import errorMsg from './utils/error-msg.js';
import {isUserInVoice} from './utils/channels.js';
import Config from './services/config.js';
import {generateDependencyReport} from '@discordjs/voice';
import {REST} from '@discordjs/rest';
import {Routes} from 'discord-api-types/v10';
import registerCommandsOnGuild from './utils/register-commands-on-guild.js';

const app = express();
app.use(express.json());

@injectable()
export default class Bot {
  private readonly client: Client;
  private readonly config: Config;
  private readonly shouldRegisterCommandsOnBot: boolean;
  private readonly commandsByName: Collection<string, Command>;
  private readonly commandsByButtonId: Collection<string, Command>;

  constructor(
    @inject(TYPES.Client) client: Client,
    @inject(TYPES.Config) config: Config
  ) {
    this.client = client;
    this.config = config;
    this.shouldRegisterCommandsOnBot = config.REGISTER_COMMANDS_ON_BOT;
    this.commandsByName = new Collection();
    this.commandsByButtonId = new Collection();
  }

  public async register(): Promise<void> {
    // Load in commands
    for (const command of container.getAll<Command>(TYPES.Command)) {
      try {
        command.slashCommand.toJSON();
      } catch (error) {
        console.error(error);
        throw new Error(`Could not serialize /${command.slashCommand.name ?? ''} to JSON`);
      }
      if (command.slashCommand.name) {
        this.commandsByName.set(command.slashCommand.name, command);
      }
      if (command.handledButtonIds) {
        for (const buttonId of command.handledButtonIds) {
          this.commandsByButtonId.set(buttonId, command);
        }
      }
    }

    // Register event handlers
    this.client.on('interactionCreate', async interaction => {
      try {
        if (interaction.isCommand()) {
          const command = this.commandsByName.get(interaction.commandName);

          if (!command || !interaction.isChatInputCommand()) {
            return;
          }

          if (!interaction.guild) {
            await interaction.reply(errorMsg('you can\'t use this bot in a DM'));
            return;
          }

          const requiresVC = command.requiresVC instanceof Function ? command.requiresVC(interaction) : command.requiresVC;
          if (requiresVC && interaction.member && !isUserInVoice(interaction.guild, interaction.member.user as User)) {
            await interaction.reply({content: errorMsg('gotta be in a voice channel'), ephemeral: true});
            return;
          }

          if (command.execute) {
            await command.execute(interaction);
          }
        } else if (interaction.isButton()) {
          const command = this.commandsByButtonId.get(interaction.customId);

          if (!command) {
            return;
          }

          if (command.handleButtonInteraction) {
            await command.handleButtonInteraction(interaction);
          }
        } else if (interaction.isAutocomplete()) {
          const command = this.commandsByName.get(interaction.commandName);

          if (!command) {
            return;
          }

          if (command.handleAutocompleteInteraction) {
            await command.handleAutocompleteInteraction(interaction);
          }
        }
      } catch (error: unknown) {
        debug(error);

        try {
          if ((interaction.isCommand() || interaction.isButton()) && (interaction.replied || interaction.deferred)) {
            await interaction.editReply(errorMsg(error as Error));
          } else if (interaction.isCommand() || interaction.isButton()) {
            await interaction.reply({content: errorMsg(error as Error), ephemeral: true});
          }
        } catch {}
      }
    });

    const spinner = ora('📡 connecting to Discord...').start();

    this.client.once('ready', async () => {
      debug(generateDependencyReport());

      // Update commands
      const rest = new REST({version: '10'}).setToken(this.config.DISCORD_TOKEN);
      if (this.shouldRegisterCommandsOnBot) {
        spinner.text = '📡 updating commands on bot...';
        await rest.put(
          Routes.applicationCommands(this.client.user!.id),
          {body: this.commandsByName.map(command => command.slashCommand.toJSON())},
        );
      } else {
        spinner.text = '📡 updating commands in all guilds...';

        await Promise.all([
          ...this.client.guilds.cache.map(async guild => {
            await registerCommandsOnGuild({
              rest,
              guildId: guild.id,
              applicationId: this.client.user!.id,
              commands: this.commandsByName.map(c => c.slashCommand),
            });
          }),
          rest.put(Routes.applicationCommands(this.client.user!.id), {body: []}),
        ]);
      }

      this.client.user!.setPresence({
        activities: [
          {
            name: this.config.BOT_ACTIVITY,
            type: this.config.BOT_ACTIVITY_TYPE,
            url: this.config.BOT_ACTIVITY_URL === '' ? undefined : this.config.BOT_ACTIVITY_URL,
          },
        ],
        status: this.config.BOT_STATUS,
      });

      spinner.succeed(`Ready! Invite the bot with https://discordapp.com/oauth2/authorize?client_id=${this.client.user?.id ?? ''}&scope=bot%20applications.commands&permissions=36700160`);
    });

    this.client.on('error', console.error);
    this.client.on('debug', debug);

    this.client.on('guildCreate', handleGuildCreate);
    this.client.on('voiceStateUpdate', handleVoiceStateUpdate);
    await this.client.login();

    // --- Express API ---
    app.post('/command/:name', async (req, res) => {
      const { name } = req.params;
      let { guildId, userId, options, voiceChannelId } = req.body;

      console.log(`[API] Received command: ${name}`);
      console.log(`[API] Body:`, JSON.stringify(req.body, null, 2));

      const command = this.commandsByName.get(name);
      if (!command) {
        console.log(`[API] Command not found: ${name}`);
        return res.status(404).json({ error: 'Command not found' });
      }

      // Find the real guild, member, channel from the Discord.js client
      const guild = this.client.guilds.cache.get(String(guildId));
      if (!guild) {
        console.log(`[API] Guild not found: ${guildId}`);
        return res.status(404).json({ error: 'Guild not found' });
      }
      const member = guild.members.cache.get(String(userId));
      if (!member) {
        console.log(`[API] Member not found: ${userId}`);
        return res.status(404).json({ error: 'Member not found' });
      }
      const channel = guild.channels.cache.get(String(voiceChannelId));
      if (!channel) {
        console.log(`[API] Channel not found: ${voiceChannelId}`);
      }

      // Build a real ChatInputCommandInteraction-like mock
      const mockInteraction = {
        guild,
        user: member.user,
        member,
        channel,
        replied: false,
        deferred: false,
        options: {
          getString: (key: string) => options?.[key],
          getBoolean: (key: string) => {
            const value = options?.[key];
            if (typeof value === 'boolean') return value;
            if (typeof value === 'string') return value === 'true';
            return undefined;
          },
          getInteger: (key: string) => {
            const value = options?.[key];
            if (typeof value === 'number') return value;
            if (typeof value === 'string' && !isNaN(Number(value))) return Number(value);
            return undefined;
          },
          getSubcommand: () => options?.subcommand,
        },
        reply: function (msg: any) {
          this.replied = true;
          console.log(`[API] Command reply:`, msg);
          return Promise.resolve(msg);
        },
        deferReply: function (opts?: any) {
          this.deferred = true;
          console.log(`[API] deferReply called`, opts);
          return Promise.resolve();
        },
        editReply: function (msg: any) {
          if (!this.deferred && !this.replied) {
            throw new Error('The reply to this interaction has not been sent or deferred.');
          }
          this.replied = true;
          console.log(`[API] editReply:`, msg);
          return Promise.resolve(msg);
        },
        isChatInputCommand: () => true,
      };

      try {
        if (typeof command.execute === 'function') {
          console.log(`[API] Executing command: ${name}`);
          await command.execute(mockInteraction as any);
          console.log(`[API] Command executed: ${name}`);
          return res.json({ success: true });
        } else {
          console.log(`[API] Command does not support execution: ${name}`);
          return res.status(400).json({ error: 'Command does not support execution' });
        }
      } catch (e) {
        const err = e as Error;
        console.log(`[API] Error executing command: ${name}`, err);
        return res.status(500).json({ error: err.message });
      }
    });

    app.listen(3003, () => console.log('API listening on port 3003'));
  }
}