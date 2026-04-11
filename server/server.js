// AALF Multiplayer Server — WebSocket-based authoritative game server
const http = require('http');
const fs = require('fs');
const path = require('path');
const { WebSocketServer } = require('ws');

const PORT = process.env.PORT || 8080;

// ── Serve static files ──
const server = http.createServer((req, res) => {
  const url = new URL(req.url, `http://${req.headers.host}`);
  let filePath = url.pathname === '/' ? '/index.html' : url.pathname;
  filePath = path.join(__dirname, '..', 'web', filePath);

  const ext = path.extname(filePath);
  const contentType = { '.html': 'text/html', '.js': 'text/javascript', '.css': 'text/css' }[ext] || 'application/octet-stream';

  fs.readFile(filePath, (err, data) => {
    if (err) {
      res.writeHead(404);
      res.end('Not found');
      return;
    }
    res.writeHead(200, { 'Content-Type': contentType });
    res.end(data);
  });
});

// ── WebSocket Server ──
const wss = new WebSocketServer({ server });

// Game rooms: seed -> { host, clients, state, tribes }
const rooms = new Map();

wss.on('connection', (ws) => {
  let playerRoom = null;
  let playerId = null;
  let playerTribe = null;

  ws.on('message', (raw) => {
    try {
      const msg = JSON.parse(raw);

      switch (msg.type) {
        case 'join': {
          const seed = msg.seed || 42;
          playerId = msg.peerId || 'p' + Math.random().toString(36).slice(2, 8);
          const roomId = 'room-' + seed;

          if (!rooms.has(roomId)) {
            // First player — create room, they're the host
            rooms.set(roomId, {
              seed,
              host: playerId,
              hostWs: ws,
              clients: new Map(),
              tribes: new Map(), // peerId -> tribeName
              state: null,
              created: Date.now(),
            });
            playerRoom = roomId;
            ws.send(JSON.stringify({ type: 'role', role: 'host', seed, playerId }));
            console.log(`[${roomId}] Host ${playerId} created room`);
          } else {
            // Join existing room as client
            const room = rooms.get(roomId);
            room.clients.set(playerId, ws);
            playerRoom = roomId;
            ws.send(JSON.stringify({ type: 'role', role: 'client', seed, playerId, hostId: room.host }));

            // Tell host to create a tribe for this player
            if (room.hostWs && room.hostWs.readyState === 1) {
              room.hostWs.send(JSON.stringify({ type: 'player_joined', peerId: playerId }));
            }

            // Send latest state to new client
            if (room.state) {
              ws.send(JSON.stringify({ type: 'state', data: room.state }));
            }

            console.log(`[${roomId}] Client ${playerId} joined (${room.clients.size + 1} players)`);
          }

          // Broadcast player count
          broadcastToRoom(roomId, { type: 'players', count: getPlayerCount(roomId), tribes: Object.fromEntries(rooms.get(roomId)?.tribes || []) });
          break;
        }

        case 'state': {
          // Host broadcasts sim state
          if (!playerRoom) break;
          const room = rooms.get(playerRoom);
          if (!room || room.host !== playerId) break;
          room.state = msg.data;
          // Forward to all clients
          for (const [cid, cws] of room.clients) {
            if (cws.readyState === 1) {
              cws.send(JSON.stringify({ type: 'state', data: msg.data }));
            }
          }
          break;
        }

        case 'command': {
          // Client sends command (decree/god power) to host
          if (!playerRoom) break;
          const room = rooms.get(playerRoom);
          if (!room) break;
          if (room.hostWs && room.hostWs.readyState === 1) {
            room.hostWs.send(JSON.stringify({ type: 'command', cmd: msg.cmd, peerId: playerId }));
          }
          break;
        }

        case 'tribe_created': {
          // Host confirms tribe was created for a player
          if (!playerRoom) break;
          const room = rooms.get(playerRoom);
          if (!room) break;
          room.tribes.set(msg.forPeer, msg.tribeName);
          // Tell the specific client
          const clientWs = room.clients.get(msg.forPeer);
          if (clientWs && clientWs.readyState === 1) {
            clientWs.send(JSON.stringify({ type: 'tribe_assigned', tribeName: msg.tribeName, tribeId: msg.tribeId }));
          }
          broadcastToRoom(playerRoom, { type: 'players', count: getPlayerCount(playerRoom), tribes: Object.fromEntries(room.tribes) });
          console.log(`[${playerRoom}] Tribe "${msg.tribeName}" created for ${msg.forPeer}`);
          break;
        }
      }
    } catch (e) {
      console.error('Message error:', e.message);
    }
  });

  ws.on('close', () => {
    if (!playerRoom) return;
    const room = rooms.get(playerRoom);
    if (!room) return;

    if (room.host === playerId) {
      // Host disconnected — promote first client to host
      room.clients.delete(playerId);
      if (room.clients.size > 0) {
        const [newHostId, newHostWs] = room.clients.entries().next().value;
        room.host = newHostId;
        room.hostWs = newHostWs;
        room.clients.delete(newHostId);
        newHostWs.send(JSON.stringify({ type: 'role', role: 'host', promoted: true }));
        console.log(`[${playerRoom}] Host left, ${newHostId} promoted`);
      } else {
        rooms.delete(playerRoom);
        console.log(`[${playerRoom}] Room closed (no players)`);
      }
    } else {
      room.clients.delete(playerId);
      room.tribes.delete(playerId);
      console.log(`[${playerRoom}] ${playerId} disconnected (${room.clients.size + 1} players)`);
    }

    if (rooms.has(playerRoom)) {
      broadcastToRoom(playerRoom, { type: 'players', count: getPlayerCount(playerRoom) });
    }
  });
});

function broadcastToRoom(roomId, msg) {
  const room = rooms.get(roomId);
  if (!room) return;
  const json = JSON.stringify(msg);
  if (room.hostWs && room.hostWs.readyState === 1) room.hostWs.send(json);
  for (const [, cws] of room.clients) {
    if (cws.readyState === 1) cws.send(json);
  }
}

function getPlayerCount(roomId) {
  const room = rooms.get(roomId);
  return room ? room.clients.size + 1 : 0;
}

server.listen(PORT, () => {
  console.log(`AALF server running on port ${PORT}`);
  console.log(`Open http://localhost:${PORT} to play`);
});
