// Connect to same-origin Socket.IO
const socket = io();

// Example: listen for server hello
socket.on('server_message', (payload) => {
  console.log('Server says:', payload);
});
