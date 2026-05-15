/**
 * Звуковые эффекты для игры Бункер
 * Использует Web Audio API — никаких внешних файлов
 */

const AudioCtx = window.AudioContext || window.webkitAudioContext;
let audioCtx = null;

function getCtx() {
    if (!audioCtx) {
        audioCtx = new AudioCtx();
    }
    return audioCtx;
}

function playTone(freq, duration, type = 'sine', volume = 0.3) {
    try {
        const ctx = getCtx();
        const osc = ctx.createOscillator();
        const gain = ctx.createGain();
        osc.type = type;
        osc.frequency.setValueAtTime(freq, ctx.currentTime);
        gain.gain.setValueAtTime(volume, ctx.currentTime);
        gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + duration);
        osc.connect(gain);
        gain.connect(ctx.destination);
        osc.start(ctx.currentTime);
        osc.stop(ctx.currentTime + duration);
    } catch (e) { /* Audio заблокирован */ }
}

function playSequence(notes, gap = 0.05) {
    let time = 0;
    notes.forEach(([freq, dur, type = 'sine', vol = 0.3]) => {
        setTimeout(() => playTone(freq, dur, type, vol), time * 1000);
        time += dur + gap;
    });
}

// Глобальный объект со звуками
window.Sound = {
    playerJoin()    { playSequence([[523, 0.1], [659, 0.1], [784, 0.15]]); },
    playerLeave()   { playSequence([[440, 0.15], [349, 0.15], [262, 0.2]]); },
    ready()         { playTone(880, 0.1, 'sine', 0.2); },
    gameStart()     { playSequence([[523, 0.15, 'triangle', 0.3], [659, 0.15, 'triangle', 0.3], [784, 0.15, 'triangle', 0.3], [1047, 0.3, 'triangle', 0.4]], 0.08); },
    reveal()        { playSequence([[300, 0.05, 'square', 0.1], [400, 0.05, 'square', 0.1], [500, 0.08, 'square', 0.15]], 0.03); },
    speech()        { playTone(440, 0.08, 'sine', 0.15); },
    aiThinking()    { playSequence([[600, 0.1, 'sawtooth', 0.1], [800, 0.1, 'sawtooth', 0.1], [1000, 0.15, 'sawtooth', 0.15]], 0.05); },
    voteCast()      { playTone(660, 0.06, 'square', 0.15); },
    votingStart()   { playSequence([[440, 0.1, 'square', 0.2], [440, 0.1, 'square', 0.2]], 0.15); },
    votingEnd()     { playSequence([[220, 0.3, 'sawtooth', 0.2], [277, 0.3, 'sawtooth', 0.2], [330, 0.4, 'sawtooth', 0.25]], 0.05); },
    eliminated()    { playSequence([[330, 0.2, 'sawtooth', 0.2], [262, 0.2, 'sawtooth', 0.2], [196, 0.4, 'sawtooth', 0.25]], 0.1); },
    roundStart()    { playSequence([[523, 0.1, 'triangle', 0.25], [659, 0.1, 'triangle', 0.25], [784, 0.2, 'triangle', 0.3]], 0.06); },
    threat()        { playSequence([[200, 0.15, 'sawtooth', 0.2], [180, 0.15, 'sawtooth', 0.2], [160, 0.25, 'sawtooth', 0.25]], 0.08); },
    gameEnd()       { playSequence([[523, 0.15, 'triangle', 0.3], [659, 0.15, 'triangle', 0.3], [784, 0.15, 'triangle', 0.3], [1047, 0.15, 'triangle', 0.3], [784, 0.15, 'triangle', 0.3], [1047, 0.4, 'triangle', 0.4]], 0.08); },
    error()         { playSequence([[200, 0.1, 'square', 0.2], [150, 0.2, 'square', 0.25]], 0.05); },
    timerTick()     { playTone(1000, 0.03, 'square', 0.15); },
    timerEnd()      { playTone(880, 0.3, 'square', 0.25); },
    question()      { playSequence([[440, 0.08], [554, 0.08], [659, 0.12]], 0.04); },
    systemMessage() { playTone(660, 0.06, 'sine', 0.12); },
};
