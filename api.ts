import express from 'express';
import container from './inversify.config.js';
import Command from './commands/index.js';
import { TYPES } from './types.js';

const app = express();
app.use(express.json());

app.post('/command/:name', async (req, res) => {
  const { name } = req.params;
  const { guildId, userId, options, voiceChannelId } = req.body;

  // Find the command
  const command = container.getAll<Command>(TYPES.Command).find(cmd => cmd.slashCommand?.name === name);
  if (!command) {
    return res.status(404).json({ error: 'Command not found' });
  }

  // Create a mock interaction object
  const guildIdStr = String(guildId);
  const userIdStr = String(userId);
  const voiceChannelIdStr = String(voiceChannelId);

  // Minimal mock for ChatInputCommandInteraction
  const mockInteraction = {
    guild: { id: guildIdStr },
    user: { id: userIdStr },
    member: {
      id: userIdStr,
      user: { id: userIdStr },
      voice: { channel: { id: voiceChannelIdStr } }
    },
    channel: { id: voiceChannelIdStr },
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
    },
    reply: (msg: any) => {
      console.log(`[API] Command reply:`, msg);
      return Promise.resolve(msg);
    },
    deferReply: (opts?: any) => {
      console.log(`[API] deferReply called`, opts);
      return Promise.resolve();
    },
    editReply: (msg: any) => {
      console.log(`[API] editReply:`, msg);
      return Promise.resolve(msg);
    },
    isChatInputCommand: () => true,
  };

  try {
    if (typeof command.execute === 'function') {
      await command.execute(mockInteraction as any);
      return res.json({ success: true });
    } else {
      return res.status(400).json({ error: 'Command does not support execution' });
    }
  } catch (e) {
    const err = e as Error;
    return res.status(500).json({ error: err.message });
  }
});

export function startApiServer() {
  app.listen(3001, () => console.log('API listening on port 3001'));
}