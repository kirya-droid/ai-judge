// ============ ГЛОБАЛЬНЫЕ ПЕРЕМЕННЫЕ ============
let ws = null;
let playerName = '';
let myId = null;
let gameStarted = false;
let myReady = false;
let currentTurn = null;
let currentPhase = 'lobby';
let currentRound = 0;
let currentBunker = null;
let currentCatastrophe = null;
let currentThreat = null;
let threatCards = [];
let currentAIPersonality = null;
let bunkerSpots = 0;
let bunkerCapacity = 0;
let playersInBunker = [];
let typingTimeout = null;
let isTyping = false;
let isSending = false;
let recognition = null;
let isListening = false;
let recognitionBaseText = '';
let myVote = null;
let players = [];

// ============ ФУНКЦИИ ПОДКЛЮЧЕНИЯ ============
function joinGame() {
    playerName = document.getElementById('playerName').value.trim();
    if (!playerName) {
        alert('> ОШИБКА: ВВЕДИТЕ ИМЯ');
        return;
    }
    document.getElementById('loginOverlay').style.display = 'none';
    document.getElementById('gameContainer').style.display = 'grid';
    connectWebSocket();
}

function connectWebSocket() {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/ws/${encodeURIComponent(playerName)}`;
    console.log('> ПОПЫТКА ПОДКЛЮЧЕНИЯ К:', wsUrl);
    ws = new WebSocket(wsUrl);
    
    ws.onopen = () => {
        console.log('> WEBSOCKET ПОДКЛЮЧЕН');
        addMessage('СИСТЕМА', '> ПОДКЛЮЧЕНИЕ К БУНКЕРУ УСТАНОВЛЕНО', 'system');
    };
    
    ws.onmessage = (event) => {
        try {
            const data = JSON.parse(event.data);
            console.log('> ПРИНЯТО:', data.type, data);
            handleWebSocketMessage(data);
        } catch (error) {
            console.error('> ОШИБКА В ОБРАБОТКЕ СООБЩЕНИЯ:', error, event.data);
        }
    };
    
    ws.onclose = () => {
        addMessage('СИСТЕМА', '⚠️ СОЕДИНЕНИЕ ПОТЕРЯНО. ПЕРЕЗАГРУЗИТЕ ТЕРМИНАЛ.', 'system');
        document.getElementById('aiStatusText').textContent = '> OFFLINE';
        document.getElementById('aiStatusText').style.color = '#f00';
    };
    
    ws.onerror = (error) => {
        console.error('> ОШИБКА WEBSOCKET:', error);
        addMessage('СИСТЕМА', '❌ ОШИБКА СОЕДИНЕНИЯ', 'system');
    };
}

// ============ ОБРАБОТЧИК СООБЩЕНИЙ ============
function handleWebSocketMessage(data) {
    switch (data.type) {
        case 'game_state':
            if (data.game) updateGameState(data.game);
            break;

        case 'game_state_update':
            // Обновляем состояние игры (например, после раскрытия карты)
            if (data.game) {
                console.log('> ОБНОВЛЕНИЕ СОСТОЯНИЯ ИГРЫ');
                // Обновляем players массив
                if (data.game.players) {
                    players = data.game.players;
                }
                updateGameState(data.game);
                // Принудительно перерисовываем карточки
                updatePlayers(players);
            }
            break;
            
        case 'player_joined':
            // При присоединении нового игрока все получают обновлённое состояние
            // game_state придёт отдельным сообщением через broadcast
            if (data.player_name) {
                addMessage('СИСТЕМА', `> 📡 ${data.player_name} ПРИСОЕДИНИЛСЯ`, 'system');
                if (typeof Sound !== 'undefined') Sound.playerJoin();
            }
            break;

        case 'player_ready':
            if (data.game) updateGameState(data.game);
            addMessage('СИСТЕМА', `> ${data.player_name} ${data.ready ? 'ГОТОВ' : 'НЕ ГОТОВ'}`, 'system');
            if (data.ready && typeof Sound !== 'undefined') Sound.ready();
            break;

        case 'player_left':
            if (data.game) updateGameState(data.game);
            addMessage('СИСТЕМА', `> ИГРОК ПОКИНУЛ БУНКЕР`, 'system');
            if (typeof Sound !== 'undefined') Sound.playerLeave();
            // Перерисовываем игроков
            if (data.game && data.game.players) {
                players = data.game.players;
                updatePlayers(players);
            }
            break;
            
        case 'game_started':
            gameStarted = true;
            console.log('> ИГРА НАЧАЛАСЬ');
            if (data.game) updateGameState(data.game);
            document.getElementById('readyButton').style.display = 'none';
            addMessage('СИСТЕМА', '> ИГРА НАЧАЛАСЬ', 'system');
            if (typeof Sound !== 'undefined') Sound.gameStart();
            break;
            
        case 'bunker_card':
            console.log('> ПОЛУЧЕНА КАРТА БУНКЕРА:', data.bunker);
            if (data.bunker) {
                currentBunker = data.bunker;
                updateBunkerCard(data.bunker);
                updateBunkerResources(data.bunker);
            }
            break;
            
        case 'catastrophe_card':
            console.log('> ПОЛУЧЕНА КАРТА КАТАСТРОФЫ:', data.catastrophe);
            if (data.catastrophe) {
                currentCatastrophe = data.catastrophe;
                addCatastropheCard(data.catastrophe);
            }
            break;
            
        case 'threat_card':
            console.log('> ПОЛУЧЕНА КАРТА УГРОЗЫ:', data.threat);
            if (data.threat) {
                currentThreat = data.threat;
                threatCards.push(data.threat);
                addThreatCard(data.threat, data.round || currentRound);
                addMessage('⚠️ НОВАЯ УГРОЗА', `${data.threat.name} - ${data.threat.description}`, 'system');
                if (typeof Sound !== 'undefined') Sound.threat();

                if (data.bunker) updateBunkerResources(data.bunker);
            }
            break;

        case 'round_started':
            currentRound = data.round;
            if (data.game) updateGameState(data.game);
            addMessage('СИСТЕМА', `> РАУНД ${currentRound} НАЧАЛСЯ`, 'system');
            if (typeof Sound !== 'undefined') Sound.roundStart();
            break;

        case 'phase_changed':
            currentPhase = data.phase;
            updatePhaseDisplay();
            addMessage('СИСТЕМА', `> ФАЗА: ${data.phase_name}`, 'system');
            // Сбрасываем currentTurn при смене фазы
            currentTurn = null;
            updateUIForGameState();
            
            // Если фаза голосования - сразу показываем кнопки
            if (currentPhase === 'voting') {
                setTimeout(() => {
                    updateVoteButtons();
                }, 100);
            }
            break;

        case 'your_reveal_turn':
            // Ваша очередь раскрывать карту
            if (data.player_id === myId) {
                addMessage('СИСТЕМА', '> ВАША ОЧЕРЕДЬ РАСКРЫВАТЬ КАРТУ!', 'system');
                showRevealModal();
            }
            break;
            
        case 'next_turn':
            currentTurn = data.player_name;
            updateCurrentSpeaker(currentTurn);
            console.log('> next_turn:', data.player_name, 'currentPhase:', currentPhase, 'playerName:', playerName);
            updateUIForGameState();

            // Если наступила наша очередь, активируем поле ввода
            if (currentTurn === playerName && (currentPhase === 'discussion' || currentPhase === 'final_word')) {
                console.log('> ВАША ОЧЕРЕДЬ! phase=' + currentPhase);
                setTimeout(() => {
                    document.getElementById('speechInput').disabled = false;
                    document.getElementById('sendButton').disabled = false;
                    document.getElementById('micButton').disabled = false;
                    document.getElementById('speechInput').focus();
                    console.log('> Поле ввода активировано');
                }, 500);
            } else {
                console.log('> НЕ ВАША ОЧЕРЕДЬ. currentTurn=' + currentTurn + ', playerName=' + playerName + ', phase=' + currentPhase);
            }
            break;
            
        case 'speech':
            const prefix = data.is_answer ? '🗨️ ' : '';
            addMessage(data.player.name.toUpperCase(), prefix + data.text, data.player.name === playerName ? 'mine' : 'other');
            break;
            
        case 'speech_analyzed':
            if (data.ai_thought) {
                addAIThought(data.ai_thought);
                if (data.ai_thought.question) {
                    addMessage('🤖 AI', `❓ ${data.ai_thought.question}`, 'ai');
                    if (data.ai_thought.player === playerName) {
                        addMessage('СИСТЕМА', '> Введите ответ в поле ниже и отправьте', 'system');
                        document.getElementById('speechInput').disabled = false;
                        document.getElementById('sendButton').disabled = false;
                        document.getElementById('micButton').disabled = false;
                        if (typeof Sound !== 'undefined') Sound.question();
                    }
                } else if (data.ai_thought.thought && data.ai_thought.thought.includes('Ответ на вопрос')) {
                    addMessage('СИСТЕМА', '> Ответ принят, ход переходит к следующему игроку', 'system');
                }
            }
            break;

        case 'ai_thinking':
            addMessage('🤖 AI', `> ${data.text}`, 'ai');
            if (typeof Sound !== 'undefined') Sound.aiThinking();
            break;
            
        case 'question':
            addMessage(`❓ ${data.from_player} -> ${data.to_player}`, data.text, 'system');
            break;
            
        case 'ai_thought':
            addAIThought(data.ai_thought);
            break;

        case 'vote_cast':
            addMessage('СИСТЕМА', `> ${data.player_name} проголосовал`, 'system');
            if (typeof Sound !== 'undefined') Sound.voteCast();
            break;
            
        case 'ai_recommendation':
            if (data.recommendation) {
                const isAdvice = data.is_advice === true;
                const title = isAdvice ? '🤖 AI СОВЕТНИК - СОВЕТ' : '🤖 AI РЕКОМЕНДУЕТ';
                const prefix = isAdvice ? 'Совет перед голосованием: ' : '';
                addMessage(title,
                    `${prefix}Исключить: ${data.recommendation.recommendation}\n\nОбоснование: ${data.recommendation.reasoning}`,
                    'ai');
            }
            break;

        case 'ai_final_decision':
            if (data.decision) {
                addMessage('⚖️ AI СУДЬЯ - ФИНАЛЬНОЕ РЕШЕНИЕ',
                    `Исключить: ${data.decision.decision}\n\nОбоснование: ${data.decision.reasoning}`,
                    'ai');
                if (typeof Sound !== 'undefined') Sound.votingEnd();
            }
            break;

        case 'voting_completed':
            addMessage('📢 ГОЛОСОВАНИЕ', `Выбыл: ${data.eliminated}`, 'system');
            hideVotingTimer();
            if (data.game) updateGameState(data.game);
            if (typeof Sound !== 'undefined') Sound.eliminated();
            break;
            
        case 'reveal':
            handleReveal(data);
            if (typeof Sound !== 'undefined') Sound.reveal();
            break;

        case 'bunker_update':
            console.log('> ОБНОВЛЕНИЕ БУНКЕРА:', data.bunker);
            if (data.bunker) updateBunkerResources(data.bunker);
            break;

        case 'game_finished':
            if (data.verdict) {
                addMessage('🏁 ИГРА ЗАВЕРШЕНА', data.verdict.message, 'system');
                const speechInput = document.getElementById('speechInput');
                const sendButton = document.getElementById('sendButton');
                const drawThreatBtn = document.getElementById('drawThreatBtn');
                if (speechInput) speechInput.disabled = true;
                if (sendButton) sendButton.disabled = true;
                if (drawThreatBtn) drawThreatBtn.disabled = true;
                if (typeof Sound !== 'undefined') Sound.gameEnd();
            }
            break;
            
        case 'system_message':
            addMessage('СИСТЕМА', `> ${data.text}`, 'system');
            break;
            
        case 'typing_start':
            showTypingIndicator(data.player_name);
            break;
            
        case 'typing_stop':
            hideTypingIndicator(data.player_name);
            break;
            
        case 'game_reset':
            resetUI();
            if (data.game) updateGameState(data.game);
            gameStarted = false;
            currentTurn = null;
            currentPhase = 'lobby';
            currentThreat = null;
            currentCatastrophe = null;
            threatCards = [];
            currentBunker = null;
            updateCurrentSpeaker(null);
            updateUIForGameState();
            addMessage('СИСТЕМА', '> ИГРА СБРОШЕНА', 'system');
            break;
            
        case 'choose_reveal':
            showRevealOptions(data.options);
            break;

        case 'voting_timer_started':
            console.log('> ТАЙМЕР ГОЛОСОВАНИЯ ЗАПУЩЕН:', data.duration, 'сек');
            startVotingTimer(data.duration);
            if (typeof Sound !== 'undefined') Sound.votingStart();
            break;

        case 'voting_timer_update':
            console.log('> ОБНОВЛЕНИЕ ТАЙМЕРА:', data.remaining, 'сек');
            updateVotingTimer(data.remaining);
            if (data.remaining <= 5 && typeof Sound !== 'undefined') Sound.timerTick();
            if (data.remaining <= 0 && typeof Sound !== 'undefined') Sound.timerEnd();
            break;

        case 'player_typing':
            setPlayerCardState(data.player_name, 'typing');
            break;

        case 'player_stop_typing':
            setPlayerCardState(data.player_name, null);
            break;

        case 'player_recording':
            setPlayerCardState(data.player_name, 'recording');
            break;

        case 'player_stop_recording':
            setPlayerCardState(data.player_name, null);
            break;

        default:
            console.log('> НЕИЗВЕСТНЫЙ ТИП СООБЩЕНИЯ:', data.type);
    }
}

function handleReveal(data) {
    let revealText = '';
    if (data.reveal_data.type === 'profession') {
        revealText = `🔓 ${data.player_name} РАСКРЫЛ ПРОФЕССИЮ: ${data.reveal_data.value}`;
    } else if (data.reveal_data.type === 'dossier') {
        const v = data.reveal_data.value;
        let parts = [`🎂 ${v.age} лет`, `♂️ ${v.gender}`];
        if (v.orientation) parts.push(`🏳️‍🌈 ${v.orientation}`);
        revealText = `🪪 ${data.player_name} РАСКРЫЛ ДОСЬЕ: ${parts.join(', ')}`;
    } else if (data.reveal_data.type === 'positive_trait') {
        revealText = `✅ ${data.player_name} РАСКРЫЛ ЧЕРТУ: ${data.reveal_data.value}`;
    } else if (data.reveal_data.type === 'negative_trait') {
        revealText = `⚠️ ${data.player_name} РАСКРЫЛ ЧЕРТУ: ${data.reveal_data.value}`;
    } else if (data.reveal_data.type === 'condition') {
        revealText = `💊 ${data.player_name} РАСКРЫЛ ЗДОРОВЬЕ: ${data.reveal_data.value.name}`;
    } else if (data.reveal_data.type === 'secret') {
        revealText = `🔒 ${data.player_name} РАСКРЫЛ СЕКРЕТ: ${data.reveal_data.value.secret}`;
    } else if (data.reveal_data.type === 'luggage') {
        revealText = `🎒 ${data.player_name} ПОКАЗАЛ БАГАЖ: ${data.reveal_data.value.name}`;
    }
    addMessage('📢 РАСКРЫТИЕ', revealText, 'system');
    console.log('> РАСКРЫТИЕ КАРТЫ:', data.player_name, data.reveal_data);
}

function resetUI() {
    document.getElementById('chat').innerHTML = '';
    document.getElementById('aiThoughts').innerHTML = '';
    document.getElementById('cardsContainer').innerHTML = '';
    
    document.getElementById('foodValue').textContent = '0';
    document.getElementById('waterValue').textContent = '0';
    document.getElementById('medicineValue').textContent = '0';
    document.getElementById('moraleValue').textContent = '0';
    document.getElementById('bunkerName').textContent = 'Загрузка...';
}

// ============ ОБНОВЛЕНИЕ СОСТОЯНИЯ ============
function updateGameState(game) {
    if (!game) {
        console.log('> НЕТ ДАННЫХ ДЛЯ ОБНОВЛЕНИЯ');
        return;
    }

    console.log('> ОБНОВЛЕНИЕ СОСТОЯНИЯ ИГРЫ:', game);
    console.log('> ИГРОКИ В СОСТОЯНИИ:', game.players);
    if (game.players) {
        game.players.forEach(p => {
            console.log(`> ИГРОК ${p.name}:`, p.character);
        });
    }

    gameStarted = game.game_started || false;
    currentPhase = game.current_phase || 'lobby';
    currentRound = game.current_round || 0;
    currentTurn = game.current_speaker;
    bunkerSpots = game.bunker_spots || 0;
    bunkerCapacity = game.bunker_capacity || 0;
    players = game.players || [];

    // Устанавливаем myId из текущего игрока
    const me = players.find(p => p.name === playerName);
    if (me) {
        myId = me.id;
        myReady = me.ready || false;
        console.log('> МОЙ ID:', myId);
    }

    // Обработка текущей очереди раскрытия
    if (game.current_reveal_player) {
        console.log('> СЕЙЧАС РАСКРЫВАЕТ:', game.current_reveal_player);
    }

    if (game.ai_available !== undefined) {
        const statusText = document.getElementById('aiStatusText');
        statusText.textContent = game.ai_available ? '> ONLINE' : '> OFFLINE';
        statusText.style.color = game.ai_available ? '#0f0' : '#ff0';
    }

    if (game.ai_personality) {
        currentAIPersonality = game.ai_personality;
        const descEl = document.getElementById('aiPersonalityDesc');
        if (game.ai_personality_desc) {
            descEl.textContent = `${game.ai_personality} — ${game.ai_personality_desc}`;
        } else {
            descEl.textContent = game.ai_personality;
        }
    }

    if (game.bunker) {
        console.log('> ОБНОВЛЯЕМ БУНКЕР ИЗ game_state:', game.bunker);
        currentBunker = game.bunker;
        updateBunkerResources(game.bunker);

        if (!document.getElementById('bunkerCard')) {
            updateBunkerCard(game.bunker);
        }
    }

    if (game.catastrophe && !document.getElementById('catastropheCard')) {
        console.log('> ДОБАВЛЯЕМ КАТАСТРОФУ ИЗ game_state');
        currentCatastrophe = game.catastrophe;
        addCatastropheCard(game.catastrophe);
    }
    
    if (game.ai_thoughts) {
        game.ai_thoughts.forEach(thought => addAIThought(thought));
    }

    // Принудительно обновляем список игроков
    console.log('> ОБНОВЛЕНИЕ ИГРОКОВ:', game.players?.length || 0);
    updatePlayers(game.players || []);
    updatePhaseDisplay();
    updateCurrentSpeaker(currentTurn);
    updateUIForGameState();
    updateVoteButtons();

    const drawBtn = document.getElementById('drawThreatBtn');
    if (drawBtn) {
        drawBtn.disabled = !gameStarted || currentPhase !== 'discussion';
    }
}

// ============ ФУНКЦИИ КАРТ ============

function addCatastropheCard(catastrophe) {
    if (!catastrophe || document.getElementById('catastropheCard')) return;
    
    const cardsContainer = document.getElementById('cardsContainer');
    const card = document.createElement('div');
    card.id = 'catastropheCard';
    card.className = 'card catastrophe';
    
    card.innerHTML = `
        <div class="card-header">🌍 КАТАСТРОФА</div>
        <div class="card-title">${catastrophe.name || 'Неизвестно'}</div>
        <div class="card-content">${catastrophe.description || 'Нет описания'}</div>
        <div class="card-stats">
            <div class="card-stat stat-neutral">⚡ ${catastrophe.effects || 'Влияет на выживание'}</div>
        </div>
    `;
    
    cardsContainer.appendChild(card);
    card.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
}

function updateBunkerCard(bunker) {
    if (!bunker) return;
    
    const cardsContainer = document.getElementById('cardsContainer');
    const oldCard = document.getElementById('bunkerCard');
    if (oldCard) oldCard.remove();
    
    const card = document.createElement('div');
    card.id = 'bunkerCard';
    card.className = 'card bunker-card';
    
    const capacity = bunker.max_capacity || 25;
    const spots = Math.floor(capacity / 2);
    
    card.innerHTML = `
        <div class="card-header">🏭 БУНКЕР</div>
        <div class="card-title">${bunker.name || 'Неизвестный бункер'}</div>
        <div class="card-content">
            <div>Вместимость: ${capacity} чел</div>
            <div>Мест: ${spots}</div>
            <div>Особенности: ${bunker.special_features || 'нет'}</div>
        </div>
    `;
    
    cardsContainer.insertBefore(card, cardsContainer.firstChild);
}

function addThreatCard(threat, round) {
    if (!threat) return;
    
    const cardsContainer = document.getElementById('cardsContainer');
    const cardId = `threat-${Date.now()}`;
    const card = document.createElement('div');
    card.id = cardId;
    card.className = 'card threat';
    
    let effectsHtml = '';
    if (threat.effects) {
        effectsHtml = '<div class="card-stats">';
        for (const [resource, value] of Object.entries(threat.effects)) {
            if (value !== 0) {
                const sign = value > 0 ? '+' : '';
                const className = value < 0 ? 'stat-negative' : 'stat-positive';
                let resourceIcon = '';
                if (resource.includes('food')) resourceIcon = '🍖';
                else if (resource.includes('water')) resourceIcon = '💧';
                else if (resource.includes('medicine')) resourceIcon = '💊';
                else if (resource.includes('morale')) resourceIcon = '❤️';
                else resourceIcon = '📊';
                
                effectsHtml += `<div class="card-stat ${className}">${resourceIcon} ${resource}: ${sign}${value}</div>`;
            }
        }
        effectsHtml += '</div>';
    }
    
    card.innerHTML = `
        <div class="card-header">⚠️ УГРОЗА РАУНДА ${round}</div>
        <div class="card-title">${threat.name || 'Неизвестная угроза'}</div>
        <div class="card-content">${threat.description || 'Нет описания'}</div>
        ${effectsHtml}
    `;
    
    cardsContainer.appendChild(card);
    card.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
}

// ============ ФУНКЦИИ БУНКЕРА ============
function updateBunkerResources(bunker) {
    if (!bunker) return;

    console.log('> ОБНОВЛЯЕМ РЕСУРСЫ БУНКЕРА:', {
        food: bunker.food_supply,
        water: bunker.water_supply,
        medicine: bunker.medicine_supply,
        morale: bunker.morale_level
    });

    // Обновляем ресурсы на AI панели
    const foodEl = document.getElementById('aiFoodValue');
    const waterEl = document.getElementById('aiWaterValue');
    const medicineEl = document.getElementById('aiMedicineValue');
    const moraleEl = document.getElementById('aiMoraleValue');

    if (foodEl) {
        foodEl.textContent = bunker.food_supply !== undefined ? bunker.food_supply : 0;
        foodEl.className = 'resource-value-compact ' + getResourceClass(bunker.food_supply);
    }
    if (waterEl) {
        waterEl.textContent = bunker.water_supply !== undefined ? bunker.water_supply : 0;
        waterEl.className = 'resource-value-compact ' + getResourceClass(bunker.water_supply);
    }
    if (medicineEl) {
        medicineEl.textContent = bunker.medicine_supply !== undefined ? bunker.medicine_supply : 0;
        medicineEl.className = 'resource-value-compact ' + getResourceClass(bunker.medicine_supply);
    }
    if (moraleEl) {
        moraleEl.textContent = bunker.morale_level !== undefined ? bunker.morale_level : 0;
        moraleEl.className = 'resource-value-compact ' + getResourceClass(bunker.morale_level);
    }
}

function getResourceClass(value) {
    if (value < 30) return 'low';
    if (value < 70) return 'medium';
    return 'high';
}

// ============ ФУНКЦИИ ИГРОКОВ ============

/**
 * Установить состояние карточки игрока (typing / recording / null)
 */
function setPlayerCardState(playerName, state) {
    const cards = document.querySelectorAll('.player-card');
    cards.forEach(card => {
        const nameEl = card.querySelector('.player-name span');
        if (nameEl) {
            const cardName = nameEl.textContent.replace(' (ВЫ)', '').trim();
            if (cardName === playerName) {
                card.classList.remove('typing', 'recording');
                if (state) {
                    card.classList.add(state);
                }
            }
        }
    });
}

function updatePlayers(activePlayers) {
    const list = document.getElementById('playersList');
    const countSpan = document.getElementById('playersCount');
    const readyBtn = document.getElementById('readyButton');
    
    list.innerHTML = '';
    
    if (countSpan) {
        countSpan.textContent = `(${activePlayers.length})`;
    }
    
    if (!gameStarted) {
        if (readyBtn) readyBtn.style.display = 'block';
    } else {
        if (readyBtn) readyBtn.style.display = 'none';
    }
    
    activePlayers.sort((a, b) => a.name.localeCompare(b.name));

    activePlayers.forEach(player => {
        const card = createPlayerCard(player);
        list.appendChild(card);
    });

    // Обновляем кнопку ГОТОВ после отрисовки
    if (!gameStarted && readyBtn) {
        readyBtn.style.display = 'block';
        if (myReady) {
            readyBtn.textContent = '[ ✓ ГОТОВ ]';
            readyBtn.classList.add('ready');
        } else {
            readyBtn.textContent = '[ ГОТОВ ]';
            readyBtn.classList.remove('ready');
        }
    }
}

function createPlayerCard(player) {
    const card = document.createElement('div');
    card.className = 'player-card';

    if (player.eliminated) {
        card.classList.add('eliminated');
    } else if (player.in_bunker) {
        card.classList.add('in-bunker');
    } else if (gameStarted && currentTurn === player.name) {
        card.classList.add('current-turn');
    }

    card.id = `player-${player.id}`;

    let statusBadge = '';
    if (player.in_bunker) {
        statusBadge = '<span class="ready-badge status-bunker">[ В БУНКЕРЕ ]</span>';
    } else if (player.eliminated) {
        statusBadge = '<span class="ready-badge status-eliminated">[ ПОГИБ ]</span>';
    } else if (!gameStarted) {
        statusBadge = player.ready ?
            '<span class="ready-badge">[ ГОТОВ ]</span>' :
            '<span class="not-ready-badge">[ ЖДЕТ ]</span>';
    }

    const isMe = player.name === playerName;
    const ageDisplay = player.character?.age || '???';
    const genderDisplay = player.character?.gender || '???';
    const orientationDisplay = player.character?.orientation || null;
    const professionDisplay = player.character?.profession || '???';
    const professionDesc = player.character?.profession_desc || '';
    const secretDisplay = player.character?.secret?.secret || '???';

    // Получаем статусы раскрытия для подсветки
    const professionRevealed = player.character?.profession_revealed || false;
    const dossierRevealed = player.character?.dossier_revealed || false;
    const luggageRevealed = player.character?.luggage_revealed || false;
    const secretRevealed = player.character?.secret_revealed || false;
    const revealedTraits = player.character?.traits_revealed || [];
    
    // Отображаем черты с подсветкой раскрытых
    const positiveTraits = (player.character?.positive_traits || []).map((t, i) => {
        if (t === '???') return `<span class="trait positive">???</span>`;
        const isRevealed = isMe && revealedTraits.includes(`positive_${i}`);
        const revealedClass = isRevealed ? ' revealed' : '';
        return `<span class="trait positive${revealedClass}">+${t}</span>`;
    }).join('');

    const negativeTraits = (player.character?.negative_traits || []).map((t, i) => {
        if (t === '???') return `<span class="trait negative">???</span>`;
        const isRevealed = isMe && revealedTraits.includes(`negative_${i}`);
        const revealedClass = isRevealed ? ' revealed' : '';
        return `<span class="trait negative${revealedClass}">-${t}</span>`;
    }).join('');

    const luggage = player.character?.luggage || {};
    const luggageName = (isMe || luggageRevealed) ? (luggage.name || 'нет') : '???';
    const secret = player.character?.secret || {};
    const secretText = isMe ? (secret.secret || 'нет') : secretDisplay;

    // Здоровье (condition)
    const condition = player.character?.condition || null;
    const conditionRevealed = player.character?.condition_revealed || false;
    let conditionHTML = '';
    if (condition) {
        const conditionClass = conditionRevealed ? ' condition revealed' : ' condition';
        const conditionName = (isMe || conditionRevealed) ? condition.name : '???';
        const conditionDesc = (isMe || conditionRevealed) ? (condition.description || '') : 'Скрыто';
        conditionHTML = `<div class="${conditionClass}" title="${conditionDesc}">💊 ${conditionName}</div>`;
    }

    // Классы для раскрытых карт
    const professionClass = professionRevealed ? ' profession revealed' : ' profession';
    const playerInfoClass = dossierRevealed ? ' player-info revealed' : ' player-info';
    const luggageClass = luggageRevealed ? ' luggage revealed' : ' luggage';
    const secretClass = secretRevealed ? ' secret revealed' : ' secret';

    // Строим блок досье
    let dossierHTML = `<span>🎂 ${ageDisplay} лет</span>`;
    dossierHTML += ` | <span>♂️ ${genderDisplay}</span>`;
    if (orientationDisplay) {
        dossierHTML += ` | <span>🏳️‍🌈 ${orientationDisplay}</span>`;
    }

    card.innerHTML = `
        <div class="player-name">
            <span>${player.name} ${isMe ? '(ВЫ)' : ''}</span>
            ${statusBadge}
        </div>
        <div class="${playerInfoClass}">
            ${dossierHTML}
        </div>
        <div class="${professionClass}" title="${professionDesc}">
            ⚕️ ${professionDisplay}
        </div>
        <div class="traits">
            ${positiveTraits}
            ${negativeTraits}
        </div>
        ${conditionHTML}
        <div class="${secretClass}">
            🔒 ${secretText}
        </div>
        <div class="${luggageClass}">
            <span>🎒 ${luggageName}</span>
        </div>
    `;

    return card;
}

// ============ ФУНКЦИИ ЧАТА ============
function addMessage(sender, text, type) {
    const chat = document.getElementById('chat');
    const message = document.createElement('div');
    message.className = `message ${type}`;
    
    const now = new Date();
    const time = `${now.getHours().toString().padStart(2, '0')}:${now.getMinutes().toString().padStart(2, '0')}:${now.getSeconds().toString().padStart(2, '0')}`;
    
    message.innerHTML = `
        <div class="sender">> ${sender}</div>
        <div style="white-space: pre-wrap; word-break: break-word;">${text.replace(/\n/g, '<br>')}</div>
        <div class="time">${time}</div>
    `;
    
    chat.appendChild(message);
    chat.scrollTo({ top: chat.scrollHeight, behavior: 'smooth' });
    
    while (chat.children.length > 100) {
        chat.removeChild(chat.firstChild);
    }
}

// ============ ФУНКЦИИ AI ============
function addAIThought(thought) {
    const thoughts = document.getElementById('aiThoughts');
    const div = document.createElement('div');
    div.className = 'thought';
    
    const thoughtText = thought.thought || (typeof thought === 'string' ? thought : '');
    const aiName = thought.ai_name || currentAIPersonality || 'AI';
    
    const existing = Array.from(thoughts.querySelectorAll('.thought')).find(t => {
        const tt = (t.querySelector('.thought-text')?.textContent || '').replace(/^>\s*/, '');
        return tt === thoughtText;
    });
    
    if (existing) return;
    
    div.innerHTML = `
        <div class="thought-header">
            <span>🤖 ${aiName}</span>
            ${thought.round ? `<span>Раунд ${thought.round}</span>` : ''}
        </div>
        <div class="thought-text">> ${thoughtText}</div>
    `;
    
    thoughts.insertBefore(div, thoughts.firstChild);
    thoughts.scrollTop = 0;
}

// ============ ФУНКЦИИ ГОЛОСОВАНИЯ ============
function updateVoteButtons() {
    const voteButtons = document.getElementById('voteButtons');
    
    if (currentPhase === 'voting' && gameStarted) {
        const alivePlayers = players.filter(p => !p.eliminated && !p.in_bunker && p.name !== playerName);
        
        if (alivePlayers.length > 0) {
            voteButtons.style.display = 'flex';
            voteButtons.innerHTML = '<span style="color:#ff0; margin-right:10px;">ГОЛОСОВАНИЕ:</span>';
            
            alivePlayers.forEach(p => {
                const btn = document.createElement('button');
                btn.className = 'vote-btn';
                btn.textContent = p.name;
                btn.onclick = () => castVote(p.id);
                if (myVote === p.id) btn.classList.add('selected');
                voteButtons.appendChild(btn);
            });
        }
    } else {
        voteButtons.style.display = 'none';
    }
}

function castVote(targetId) {
    if (!ws || ws.readyState !== WebSocket.OPEN) return;
    myVote = targetId;
    ws.send(JSON.stringify({ type: 'vote', target_id: targetId }));
    updateVoteButtons();
}

function startVoting() {
    if (!ws || ws.readyState !== WebSocket.OPEN) return;
    ws.send(JSON.stringify({ type: 'start_voting' }));
}

// ============ ТАЙМЕР ГОЛОСОВАНИЯ ============
let votingTimerElement = null;
let votingTimerInterval = null;

function startVotingTimer(duration) {
    console.log('> ЗАПУСК ТАЙМЕРА ГОЛОСОВАНИЯ:', duration, 'сек');
    
    // Очищаем предыдущий таймер если был
    if (votingTimerInterval) {
        clearInterval(votingTimerInterval);
        votingTimerInterval = null;
    }
    
    // Создаём или показываем элемент таймера
    if (!votingTimerElement) {
        votingTimerElement = document.createElement('div');
        votingTimerElement.id = 'votingTimer';
        votingTimerElement.style.cssText = `
            position: fixed;
            top: 20px;
            left: 50%;
            transform: translateX(-50%);
            background: rgba(0, 0, 0, 0.9);
            border: 3px solid #f00;
            color: #f00;
            padding: 15px 30px;
            font-size: 2rem;
            font-family: 'Courier New', monospace;
            z-index: 100000;
            box-shadow: 0 0 30px rgba(255, 0, 0, 0.5);
            animation: pulse 1s infinite;
        `;
        document.body.appendChild(votingTimerElement);
    }
    
    let remaining = duration;
    votingTimerElement.textContent = `⏳ ГОЛОСОВАНИЕ: ${remaining} сек`;
    votingTimerElement.style.display = 'block';
    
    // Запускаем обратный отсчёт
    votingTimerInterval = setInterval(() => {
        remaining--;
        if (votingTimerElement) {
            votingTimerElement.textContent = `⏳ ГОЛОСОВАНИЕ: ${remaining} сек`;
            
            // Меняем цвет когда мало времени
            if (remaining <= 10) {
                votingTimerElement.style.borderColor = '#ff0';
                votingTimerElement.style.color = '#ff0';
            }
            if (remaining <= 5) {
                votingTimerElement.style.borderColor = '#f00';
                votingTimerElement.style.color = '#f00';
            }
        }
        if (remaining <= 0) {
            clearInterval(votingTimerInterval);
            votingTimerInterval = null;
        }
    }, 1000);
}

function updateVotingTimer(remaining) {
    // Эта функция теперь не нужна, таймер обновляется локально
    console.log('> ОБНОВЛЕНИЕ ТАЙМЕРА ОТ СЕРВЕРА:', remaining, 'сек');
}

function hideVotingTimer() {
    if (votingTimerInterval) {
        clearInterval(votingTimerInterval);
        votingTimerInterval = null;
    }
    if (votingTimerElement) {
        votingTimerElement.style.display = 'none';
    }
}

// Добавляем CSS анимацию пульсации
const style = document.createElement('style');
style.textContent = `
    @keyframes pulse {
        0% { box-shadow: 0 0 30px rgba(255, 0, 0, 0.5); }
        50% { box-shadow: 0 0 50px rgba(255, 0, 0, 0.8); }
        100% { box-shadow: 0 0 30px rgba(255, 0, 0, 0.5); }
    }
`;
document.head.appendChild(style);

// ============ ФУНКЦИИ РАСКРЫТИЯ ============
function showRevealModal() {
    // Показываем модальное окно для раскрытия карты в фазе reveal_card
    if (window.revealModal) document.body.removeChild(window.revealModal);

    const modal = document.createElement('div');
    modal.style.position = 'fixed';
    modal.style.top = '50%';
    modal.style.left = '50%';
    modal.style.transform = 'translate(-50%, -50%)';
    modal.style.background = 'rgba(15, 15, 15, 0.85)';  // Ещё более прозрачный (85%)
    modal.style.border = '2px solid #ff0';  // Тоньше рамка
    modal.style.padding = '20px';
    modal.style.zIndex = '10000';
    modal.style.maxWidth = '400px';
    modal.style.width = '90%';
    modal.style.boxShadow = '0 0 30px rgba(255,255,0,0.2)';  // Ещё меньше свечение
    modal.style.maxHeight = '80vh';
    modal.style.overflowY = 'auto';
    modal.style.backdropFilter = 'blur(3px)';  // Меньше размытие

    // Получаем доступные опции для раскрытия из данных игрока
    const myPlayer = players.find(p => p.name === playerName);
    const options = myPlayer?.character?.can_reveal || [];

    if (options.length === 0) {
        modal.innerHTML = `<div style="color: #f00; text-align: center;">⚠️ Нечего раскрывать!</div>`;
        setTimeout(() => {
            if (window.revealModal) {
                document.body.removeChild(window.revealModal);
                window.revealModal = null;
            }
        }, 2000);
    } else {
        modal.innerHTML = `
            <div style="text-align: center; margin-bottom: 15px; color: #ff0; font-size: 1.1rem;">
                🔓 ВАША ОЧЕРЕДЬ - РАСКРОЙТЕ КАРТУ
            </div>
            <div style="display: flex; flex-direction: column; gap: 8px;">
                ${options.map(opt => `
                    <button onclick="window.sendRevealCard('${opt.type}')"
                        style="background: transparent; border: 2px solid #ff0; color: #ff0; padding: 8px;
                               cursor: pointer; font-size: 0.9rem; text-align: left; display: flex; align-items: center; gap: 10px;
                               transition: all 0.3s;"
                        onmouseover="this.style.background='#ff0'; this.style.color='#000'"
                        onmouseout="this.style.background='transparent'; this.style.color='#ff0'">
                        <span style="font-size: 1.3rem;">${opt.emoji}</span>
                        <span>${opt.name}</span>
                    </button>
                `).join('')}
            </div>
        `;
    }

    document.body.appendChild(modal);
    window.revealModal = modal;
}

window.sendRevealCard = function(optionType) {
    if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ type: 'reveal_card', option: optionType }));
    }
    if (window.revealModal) {
        document.body.removeChild(window.revealModal);
        window.revealModal = null;
    }
};

function showRevealOptions(options) {
    if (!options || options.length === 0) return;
    
    if (window.revealModal) document.body.removeChild(window.revealModal);
    
    const modal = document.createElement('div');
    modal.style.position = 'fixed';
    modal.style.top = '50%';
    modal.style.left = '50%';
    modal.style.transform = 'translate(-50%, -50%)';
    modal.style.background = '#0f0f0f';
    modal.style.border = '3px solid #0f0';
    modal.style.padding = '20px';
    modal.style.zIndex = '10000';
    modal.style.maxWidth = '400px';
    modal.style.width = '90%';
    modal.style.boxShadow = '0 0 50px rgba(0,255,0,0.5)';
    modal.style.maxHeight = '80vh';
    modal.style.overflowY = 'auto';
    
    modal.innerHTML = `
        <div style="text-align: center; margin-bottom: 15px; color: #0f0; font-size: 1.1rem;">
            🔓 ВЫБЕРИТЕ КАРТУ ДЛЯ РАСКРЫТИЯ
        </div>
        <div style="display: flex; flex-direction: column; gap: 8px;">
            ${options.map(opt => `
                <button onclick="window.selectReveal('${opt.type}')" 
                    style="background: transparent; border: 2px solid #0f0; color: #0f0; padding: 8px; 
                           cursor: pointer; font-size: 0.9rem; text-align: left; display: flex; align-items: center; gap: 10px;
                           transition: all 0.3s;"
                    onmouseover="this.style.background='#0f0'; this.style.color='#000'"
                    onmouseout="this.style.background='transparent'; this.style.color='#0f0'">
                    <span style="font-size: 1.3rem;">${opt.emoji}</span>
                    <span>${opt.name}</span>
                </button>
            `).join('')}
            <button onclick="window.skipReveal()" 
                style="background: transparent; border: 2px solid #f00; color: #f00; padding: 8px; 
                       cursor: pointer; font-size: 0.9rem; margin-top: 10px;
                       transition: all 0.3s;"
                onmouseover="this.style.background='#f00'; this.style.color='#fff'"
                onmouseout="this.style.background='transparent'; this.style.color='#f00'">
                🔇 НИЧЕГО НЕ РАСКРЫВАТЬ
            </button>
        </div>
    `;
    
    document.body.appendChild(modal);
    window.revealModal = modal;
}

window.selectReveal = function(optionType) {
    if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ type: 'choose_reveal', option: optionType }));
    }
    if (window.revealModal) {
        document.body.removeChild(window.revealModal);
        window.revealModal = null;
    }
};

window.skipReveal = function() {
    if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ type: 'skip_reveal' }));
    }
    if (window.revealModal) {
        document.body.removeChild(window.revealModal);
        window.revealModal = null;
    }
};

// ============ ФУНКЦИИ ИНТЕРФЕЙСА ============
function updatePhaseDisplay() {
    const phaseDisplay = document.getElementById('phaseDisplay');
    const phases = {
        'lobby': '>> ОЖИДАНИЕ ИГРОКОВ <<',
        'round_start': `>> РАУНД ${currentRound} <<`,
        'reveal_card': `>> РАУНД ${currentRound} - РАСКРЫТИЕ КАРТ <<`,
        'discussion': `>> ОБСУЖДЕНИЕ - РАУНД ${currentRound} <<`,
        'final_word': `>> ФИНАЛЬНОЕ СЛОВО - РАУНД ${currentRound} <<`,
        'voting': `>> ГОЛОСОВАНИЕ - РАУНД ${currentRound} <<`,
        'reveal': '>> РАСКРЫТИЕ КАРТЫ ВЫБЫВШЕГО <<',
        'results': '>> РЕЗУЛЬТАТЫ <<'
    };
    phaseDisplay.textContent = phases[currentPhase] || `>> ${currentPhase.toUpperCase()} <<`;
}

function updateUIForGameState() {
    const speechInput = document.getElementById('speechInput');
    const sendButton = document.getElementById('sendButton');
    const micButton = document.getElementById('micButton');
    const actionButtons = document.getElementById('actionButtons');

    console.log('> ОБНОВЛЕНИЕ UI:', {
        gameStarted,
        currentPhase,
        currentTurn,
        playerName,
        isMyTurn: currentTurn === playerName
    });

    if (!gameStarted) {
        speechInput.disabled = true;
        sendButton.disabled = true;
        if (micButton) micButton.disabled = true;
        if (actionButtons) actionButtons.style.display = 'none';
        speechInput.placeholder = '> ОЖИДАНИЕ НАЧАЛА ИГРЫ...';
        updateVoteButtons();
        return;
    }

    switch (currentPhase) {
        case 'reveal_card':
            // Фаза раскрытия карт - игрок ждёт модальное окно
            // Но можно отвечать на вопросы AI
            speechInput.disabled = false;
            sendButton.disabled = false;
            if (micButton) micButton.disabled = false;
            speechInput.placeholder = '> ОТВЕТ НА ВОПРОС AI...';
            actionButtons.style.display = 'none';
            break;

        case 'final_word':
            // Финальное слово - каждый говорит по очереди
            if (currentTurn === playerName) {
                speechInput.disabled = false;
                sendButton.disabled = false;
                if (micButton) micButton.disabled = false;
                speechInput.placeholder = '> РАССКАЖИТЕ ПОЧЕМУ ВАС ОСТАВИТЬ...';
                speechInput.focus();
            } else {
                speechInput.disabled = true;
                sendButton.disabled = true;
                if (micButton) micButton.disabled = true;
                speechInput.placeholder = `> ОЖИДАНИЕ ОЧЕРЕДИ (СЕЙЧАС ГОВОРИТ: ${currentTurn || 'НИКТО'})...`;
            }
            actionButtons.style.display = 'none';
            break;

        case 'discussion':
            if (currentTurn === playerName) {
                speechInput.disabled = false;
                sendButton.disabled = false;
                if (micButton) micButton.disabled = false;
                speechInput.placeholder = '> ВАША РЕЧЬ...';
                speechInput.focus();
                console.log('> ВАША ОЧЕРЕДЬ ГОВОРИТЬ');
            } else {
                speechInput.disabled = true;
                sendButton.disabled = true;
                if (micButton) micButton.disabled = true;
                speechInput.placeholder = `> ОЖИДАНИЕ ОЧЕРЕДИ (СЕЙЧАС ГОВОРИТ: ${currentTurn || 'НИКТО'})...`;
                console.log('> НЕ ВАША ОЧЕРЕДЬ');
            }
            actionButtons.style.display = 'none';
            break;

        case 'voting':
            speechInput.disabled = true;
            sendButton.disabled = true;
            if (micButton) micButton.disabled = true;
            speechInput.placeholder = '> ИДЕТ ГОЛОСОВАНИЕ...';
            actionButtons.style.display = 'none';
            break;

        case 'round_start':
            speechInput.disabled = true;
            sendButton.disabled = true;
            if (micButton) micButton.disabled = true;
            speechInput.placeholder = '> НАЧАЛО РАУНДА...';
            actionButtons.style.display = 'none';
            break;

        default:
            speechInput.disabled = true;
            sendButton.disabled = true;
            if (micButton) micButton.disabled = true;
            actionButtons.style.display = 'none';
    }
    
    // Обновляем кнопки голосования
    updateVoteButtons();
}

function updateCurrentSpeaker(speakerName) {
    const indicator = document.getElementById('currentSpeakerIndicator');
    if (indicator) {
        indicator.textContent = `🎤 СЕЙЧАС ГОВОРИТ: ${speakerName || 'НИКТО'}`;
    }
}

// ============ ФУНКЦИИ ДЕЙСТВИЙ ============
function toggleReady() {
    if (!ws || ws.readyState !== WebSocket.OPEN) {
        console.log('> НЕЛЬЗЯ НАЖАТЬ ГОТОВ: WebSocket не подключен');
        return;
    }
    console.log('> НАЖАТА КНОПКА ГОТОВ, myId:', myId);
    ws.send(JSON.stringify({ type: "ready" }));
}

function resetGame() {
    if (!ws || ws.readyState !== WebSocket.OPEN) return;
    if (!confirm('Сбросить состояние игры для всех игроков?')) return;
    ws.send(JSON.stringify({ type: 'reset_game' }));
}

function sendMessage() {
    if (isSending) return;
    const input = document.getElementById('speechInput');
    const text = input.value.trim();

    if (!text || text.length < 1) return;

    isSending = true;

    if (currentPhase === 'discussion' || currentPhase === 'final_word') {
        ws.send(JSON.stringify({ type: 'speech', text: text }));
    }

    input.value = '';
    setTimeout(() => { isSending = false; }, 1000);
}

// ============ ИНДИКАТОР ПЕЧАТИ ============
function setupTypingIndicator() {
    const speechInput = document.getElementById('speechInput');
    speechInput.addEventListener('input', () => {
        if (!gameStarted || (currentPhase !== 'discussion' && currentPhase !== 'final_word')) {
            if (isTyping) {
                isTyping = false;
                if (ws && ws.readyState === WebSocket.OPEN) {
                    ws.send(JSON.stringify({ type: "typing_stop" }));
                }
            }
            return;
        }
        if (!isTyping) {
            isTyping = true;
            if (ws && ws.readyState === WebSocket.OPEN) {
                ws.send(JSON.stringify({ type: "typing_start" }));
            }
        }
        if (typingTimeout) clearTimeout(typingTimeout);
        typingTimeout = setTimeout(() => {
            if (isTyping) {
                isTyping = false;
                if (ws && ws.readyState === WebSocket.OPEN) {
                    ws.send(JSON.stringify({ type: "typing_stop" }));
                }
            }
        }, 2000);
    });
    
    speechInput.addEventListener('blur', () => {
        if (isTyping) {
            isTyping = false;
            if (ws && ws.readyState === WebSocket.OPEN) {
                ws.send(JSON.stringify({ type: "typing_stop" }));
            }
        }
        if (typingTimeout) clearTimeout(typingTimeout);
    });
}

function showTypingIndicator(playerName) {
    hideAllTypingIndicators();
    const players = document.querySelectorAll('.player-card');
    players.forEach(card => {
        const nameSpan = card.querySelector('.player-name span');
        if (nameSpan && nameSpan.textContent.includes(playerName)) {
            if (!card.querySelector('.typing-indicator')) {
                const indicator = document.createElement('div');
                indicator.className = 'typing-indicator';
                indicator.textContent = '✎ печатает...';
                card.appendChild(indicator);
            }
        }
    });
}

function hideTypingIndicator(playerName) {
    document.querySelectorAll('.typing-indicator').forEach(ind => ind.remove());
}

function hideAllTypingIndicators() {
    document.querySelectorAll('.typing-indicator').forEach(ind => ind.remove());
}

// ============ ГОЛОСОВОЙ ВВОД ============
function initSpeechRecognition() {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRecognition) {
        console.log('Браузер не поддерживает голосовой ввод');
        document.getElementById('micButton').style.display = 'none';
        return false;
    }
    
    recognition = new SpeechRecognition();
    recognition.lang = 'ru-RU';
    recognition.continuous = true;
    recognition.interimResults = true;
    
    recognition.onresult = (event) => {
        const speechInput = document.getElementById('speechInput');
        let interim = '';
        let finalConcat = '';
        
        for (let i = event.resultIndex; i < event.results.length; ++i) {
            const res = event.results[i][0].transcript || '';
            if (event.results[i].isFinal) {
                finalConcat += res + ' ';
            } else {
                interim = res;
            }
        }
        
        if (finalConcat) {
            recognitionBaseText = (recognitionBaseText || '') + finalConcat;
            recognitionBaseText = recognitionBaseText.trim() + ' ';
            speechInput.value = recognitionBaseText.trim();
            speechInput.selectionStart = speechInput.selectionEnd = speechInput.value.length;
        }
        
        if (!finalConcat && interim) {
            speechInput.value = (recognitionBaseText || '') + interim + '...';
        }
    };
    
    recognition.onerror = (event) => {
        console.error('Ошибка распознавания:', event.error);
        stopListening();
    };
    
    recognition.onend = () => stopListening();
    
    return true;
}

function toggleMicrophone() {
    if (!recognition && !initSpeechRecognition()) return;
    isListening ? stopListening() : startListening();
}

function startListening() {
    const speechInput = document.getElementById('speechInput');
    const micButton = document.getElementById('micButton');

    if (!gameStarted || currentPhase !== 'discussion' || currentTurn !== playerName) {
        addMessage('СИСТЕМА', '> ⏳ Сейчас нельзя использовать микрофон', 'system');
        return;
    }

    recognitionBaseText = (speechInput.value || '').trim() ? (speechInput.value.trim() + ' ') : '';

    try {
        recognition.start();
        isListening = true;
        micButton.classList.add('listening');
        micButton.textContent = '⏹️';
        speechInput.placeholder = '> ГОВОРИТЕ...';
        // Показываем запись на карточке
        setPlayerCardState(playerName, 'recording');
        if (ws && ws.readyState === WebSocket.OPEN) {
            ws.send(JSON.stringify({ type: "recording_start" }));
        }
    } catch (e) {
        console.error('Ошибка запуска:', e);
        stopListening();
    }
}

function stopListening() {
    if (recognition && isListening) {
        try { recognition.stop(); } catch (e) {}
    }

    isListening = false;
    const micButton = document.getElementById('micButton');
    const speechInput = document.getElementById('speechInput');

    if (micButton) {
        micButton.classList.remove('listening');
        micButton.textContent = '🎤';
    }

    if (speechInput) {
        speechInput.placeholder = currentTurn === playerName ? '> ВАША РЕЧЬ...' : '> ОЖИДАНИЕ ОЧЕРЕДИ...';
    }

    // Убираем запись с карточки
    setPlayerCardState(playerName, null);
    if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ type: "recording_stop" }));
    }
}

// ============ ИНИЦИАЛИЗАЦИЯ ============
document.addEventListener('DOMContentLoaded', () => {
    console.log('> СТРАНИЦА ЗАГРУЖЕНА');
    document.getElementById('playerName').focus();
    setupTypingIndicator();
    initSpeechRecognition();
    
    document.getElementById('speechInput').addEventListener('keypress', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendMessage();
        }
    });
});