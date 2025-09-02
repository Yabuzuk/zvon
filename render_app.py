import asyncio
import json
import os
from aiohttp import web
import uuid

class VoiceChat:
    def __init__(self):
        self.rooms = {}
        self.connections = {}
    
    def create_app(self):
        app = web.Application()
        app.router.add_get('/', self.index)
        app.router.add_get('/room/{room_id}', self.room)
        app.router.add_get('/ws', self.websocket_handler)
        app.router.add_post('/create-room', self.create_room)
        return app
    
    async def index(self, request):
        html = '''<!DOCTYPE html>
<html><head><title>Voice Chat</title>
<style>body{font-family:Arial;max-width:600px;margin:50px auto;padding:20px}
.btn{background:#4CAF50;color:white;padding:15px 30px;border:none;border-radius:5px;cursor:pointer;font-size:16px}
.room-link{background:#f0f0f0;padding:15px;border-radius:5px;margin:20px 0}
input{padding:10px;width:200px;border:1px solid #ddd;border-radius:5px}</style>
</head><body>
<h1>🎤 Voice Chat</h1>
<input type="text" id="roomName" placeholder="Название комнаты" value="Моя комната">
<button class="btn" onclick="createRoom()">Создать комнату</button>
<div id="result"></div>
<script>
async function createRoom(){
const name=document.getElementById('roomName').value||'Комната';
const response=await fetch('/create-room',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({name:name})});
const data=await response.json();
const link=`${window.location.origin}/room/${data.room_id}`;
document.getElementById('result').innerHTML=`<div class="room-link"><h3>Комната создана!</h3><p><a href="${link}" target="_blank">${link}</a></p><button class="btn" onclick="navigator.clipboard.writeText('${link}')">Копировать</button></div>`;
}
</script></body></html>'''
        return web.Response(text=html, content_type='text/html')
    
    async def create_room(self, request):
        data = await request.json()
        room_id = str(uuid.uuid4())[:8]
        self.rooms[room_id] = {'name': data.get('name', 'Комната'), 'users': {}}
        return web.json_response({'room_id': room_id})
    
    async def room(self, request):
        room_id = request.match_info['room_id']
        if room_id not in self.rooms:
            self.rooms[room_id] = {'name': f'Комната {room_id}', 'users': {}}
        
        html = '''<!DOCTYPE html>
<html><head><title>Voice Chat Room</title>
<style>body{font-family:Arial;margin:0;padding:20px;background:#1a1a1a;color:white}
.container{max-width:800px;margin:0 auto}.controls{text-align:center;margin:20px 0}
.btn{padding:15px 30px;margin:10px;border:none;border-radius:50px;cursor:pointer;font-size:16px}
.btn.active{background:#4CAF50;color:white}.btn.inactive{background:#f44336;color:white}
.btn.neutral{background:#666;color:white}.status{background:#333;padding:15px;border-radius:10px;margin:20px 0}
.users{background:#333;padding:15px;border-radius:10px}</style>
</head><body>
<div class="container">
<h1>🎤 Голосовая комната</h1>
<div class="status" id="status">Подключение...</div>
<div class="controls">
<button class="btn neutral" id="micBtn">🎤 Включить микрофон</button>
<button class="btn neutral" onclick="leaveRoom()">❌ Покинуть</button>
</div>
<div class="users"><h3>Участники:</h3><div id="usersList">Загрузка...</div></div>
<div id="audioContainer" style="display:none;"></div>
</div>
<script>
const roomId=window.location.pathname.split('/')[2];
const userId='user_'+Math.random().toString(36).substr(2,9);
let ws,localStream,peerConnections=new Map();
const iceServers=[{urls:['stun:stun.l.google.com:19302']}];

function init(){
connectWebSocket();
document.getElementById('micBtn').onclick=toggleMic;
// Разрешаем аудио при любом клике
document.addEventListener('click',()=>{
document.querySelectorAll('audio').forEach(a=>a.play().catch(()=>{}));
},{passive:true});
}

function connectWebSocket(){
const protocol=location.protocol==='https:'?'wss:':'ws:';
ws=new WebSocket(`${protocol}//${location.host}/ws`);
ws.onopen=async()=>{
updateStatus('Подключено к серверу');
console.log('Присоединяемся к комнате',roomId,'как',userId);
try{
localStream=await navigator.mediaDevices.getUserMedia({audio:true});
document.getElementById('micBtn').textContent='🎤 Включен';
document.getElementById('micBtn').className='btn active';
updateStatus('Микрофон автоматически включен');
}catch(e){
console.log('Ошибка автовключения микрофона:',e);
}
ws.send(JSON.stringify({type:'join',room_id:roomId,user_id:userId}));
};
ws.onmessage=(event)=>{const data=JSON.parse(event.data);handleMessage(data)};
ws.onclose=()=>updateStatus('Отключено')
}

async function handleMessage(data){
switch(data.type){
case 'users':
console.log('Получен список пользователей:',data.users);
updateUsers(data.users);break;
case 'user_joined':
updateStatus(`Пользователь ${data.user_id} присоединился`);
if(data.user_id!==userId)await createPeerConnection(data.user_id,true);break;
case 'offer':await handleOffer(data);break;
case 'answer':await handleAnswer(data);break;
case 'ice-candidate':await handleIceCandidate(data);break;
}}

async function createPeerConnection(peerId,createOffer){
console.log('Создаем соединение с',peerId,'с локальным потоком:',!!localStream);
const pc=new RTCPeerConnection({iceServers});
peerConnections.set(peerId,pc);
if(localStream){
console.log('Добавляем треки к новому соединению');
localStream.getTracks().forEach(track=>{
pc.addTrack(track,localStream);
console.log('Трек добавлен:',track.kind);
});
}
pc.ontrack=(event)=>{
console.log('Получен аудио поток от',peerId);
let audio=document.getElementById('audio_'+peerId);
if(!audio){
audio=document.createElement('audio');
audio.id='audio_'+peerId;
audio.autoplay=true;
audio.controls=false;
document.getElementById('audioContainer').appendChild(audio);
}
audio.srcObject=event.streams[0];
audio.play().catch(()=>{});
console.log('Аудио элемент создан для',peerId);
updateStatus(`Получаю аудио от ${peerId}`);
};
pc.onicecandidate=(event)=>{if(event.candidate)ws.send(JSON.stringify({type:'ice-candidate',target:peerId,candidate:event.candidate}))};
if(createOffer){const offer=await pc.createOffer();await pc.setLocalDescription(offer);ws.send(JSON.stringify({type:'offer',target:peerId,offer:offer}))}
}

async function handleOffer(data){
const pc=new RTCPeerConnection({iceServers});
peerConnections.set(data.from,pc);
if(localStream)localStream.getTracks().forEach(track=>pc.addTrack(track,localStream));
pc.ontrack=(event)=>{
console.log('Получен аудио поток от',data.from);
let audio=document.getElementById('audio_'+data.from);
if(!audio){
audio=document.createElement('audio');
audio.id='audio_'+data.from;
audio.autoplay=true;
audio.controls=false;
document.getElementById('audioContainer').appendChild(audio);
}
audio.srcObject=event.streams[0];
audio.play().then(()=>{
console.log('Аудио запущено для',data.from);
updateStatus(`Слышу ${data.from}`);
}).catch(e=>{
console.log('Ошибка воспроизведения:',e);
updateStatus('Ошибка аудио: '+e.message);
});
};
pc.onicecandidate=(event)=>{if(event.candidate)ws.send(JSON.stringify({type:'ice-candidate',target:data.from,candidate:event.candidate}))};
await pc.setRemoteDescription(data.offer);
const answer=await pc.createAnswer();
await pc.setLocalDescription(answer);
ws.send(JSON.stringify({type:'answer',target:data.from,answer:answer}))
}

async function handleAnswer(data){
const pc=peerConnections.get(data.from);
if(pc)await pc.setRemoteDescription(data.answer)
}

async function handleIceCandidate(data){
const pc=peerConnections.get(data.from);
if(pc)await pc.addIceCandidate(data.candidate)
}

async function toggleMic(){
const btn=document.getElementById('micBtn');
if(!localStream){
try{
localStream=await navigator.mediaDevices.getUserMedia({
audio:{
echoCancellation:true,
noiseSuppression:true,
autoGainControl:true,
sampleRate:48000,
channelCount:1
}
});
btn.textContent='🎤 HD Микрофон';btn.className='btn active';
updateStatus('Микрофон HD включен');
peerConnections.forEach(async(pc,peerId)=>{
console.log('Пересоздаем оффер для',peerId);
localStream.getTracks().forEach(track=>pc.addTrack(track,localStream));
const offer=await pc.createOffer();
await pc.setLocalDescription(offer);
ws.send(JSON.stringify({type:'offer',target:peerId,offer:offer}));
})
}catch(error){updateStatus('Ошибка: '+error.message);btn.textContent='❌ Ошибка';btn.className='btn inactive'}
}else{
const audioTrack=localStream.getAudioTracks()[0];
if(audioTrack){
audioTrack.enabled=!audioTrack.enabled;
btn.textContent=audioTrack.enabled?'🎤 Включен':'🎤 Выключен';
btn.className=audioTrack.enabled?'btn active':'btn inactive';
updateStatus(audioTrack.enabled?'Микрофон включен':'Микрофон выключен')
}}}

function updateStatus(message){document.getElementById('status').textContent=message}
function updateUsers(users){
console.log('Обновляем список пользователей:',users);
const list=users.map(user=>`👤 ${user}`).join('<br>');
document.getElementById('usersList').innerHTML=list||'Нет участников';
updateStatus(`Участников в комнате: ${users.length}`);
}
function leaveRoom(){if(confirm('Покинуть комнату?'))window.close()}
init();
</script></body></html>'''
        return web.Response(text=html, content_type='text/html')
    
    async def websocket_handler(self, request):
        ws = web.WebSocketResponse()
        await ws.prepare(request)
        
        user_id = None
        room_id = None
        
        async for msg in ws:
            if msg.type == web.WSMsgType.TEXT:
                try:
                    data = json.loads(msg.data)
                    
                    if data['type'] == 'join':
                        user_id = data['user_id']
                        room_id = data['room_id']
                        
                        if room_id not in self.rooms:
                            self.rooms[room_id] = {'name': f'Комната {room_id}', 'users': {}}
                        
                        self.rooms[room_id]['users'][user_id] = ws
                        self.connections[ws] = {'user_id': user_id, 'room_id': room_id}
                        print(f'Пользователь {user_id} присоединился к комнате {room_id}')
                        
                        await self.broadcast_to_room(room_id, {'type': 'user_joined', 'user_id': user_id})
                        
                        # Уведомляем всех о новом списке пользователей
                        users = list(self.rooms[room_id]['users'].keys())
                        await self.broadcast_to_room(room_id, {'type': 'users', 'users': users})
                        
                        users = list(self.rooms[room_id]['users'].keys())
                        print(f'Отправляем список пользователей: {users}')
                        await ws.send_str(json.dumps({'type': 'users', 'users': users}))
                    
                    elif data['type'] in ['offer', 'answer', 'ice-candidate']:
                        target_id = data['target']
                        if room_id and target_id in self.rooms[room_id]['users']:
                            target_ws = self.rooms[room_id]['users'][target_id]
                            data['from'] = user_id
                            await target_ws.send_str(json.dumps(data))
                
                except:
                    pass
        
        if ws in self.connections:
            conn_info = self.connections[ws]
            user_id = conn_info['user_id']
            room_id = conn_info['room_id']
            
            if room_id in self.rooms and user_id in self.rooms[room_id]['users']:
                del self.rooms[room_id]['users'][user_id]
            
            del self.connections[ws]
        
        return ws
    
    async def broadcast_to_room(self, room_id, message):
        if room_id in self.rooms:
            for ws in self.rooms[room_id]['users'].values():
                try:
                    await ws.send_str(json.dumps(message))
                except:
                    pass

def create_app():
    return VoiceChat().create_app()

if __name__ == '__main__':
    app = create_app()
    port = int(os.environ.get('PORT', 10000))
    web.run_app(app, host='0.0.0.0', port=port)
