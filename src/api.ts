import express from 'express';
import container from './inversify.config.js';
import Command from './commands/index.js';

const app = express();
app.use(express.json());

app.post('/command/:name', async (req, res) => {
  const { name } = req.params;
  const { guildId, userId, options } = req.body;

  // Find the command
  const command = container.getAll<Command>('Command').find(cmd => cmd.slashCommand.name === name);
  if (!command) {
    return res.status(404).json({ error: 'Command not found' });
  }

  // You need to create a mock interaction object or refactor your command handlers to allow direct calls.
  // For now, just call a method if you have one (e.g., play(guildId, userId, query))
  if (name === 'play' && command.play) {
    try {
      await command.play(guildId, userId, options.query);
      return res.json({ success: true });
    } catch (e) {
      return res.status(500).json({ error: e.message });
    }
  }

  return res.status(400).json({ error: 'Not implemented for this command' });
});

export function startApiServer() {
  app.listen(3001, () => console.log('API listening on port 3001'));
}