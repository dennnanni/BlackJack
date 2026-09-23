const gameArea = document.getElementById("game-area");
const me = gameArea.dataset.username;
let balance = parseFloat(gameArea.dataset.balance);
let myBet = 0;
let sittingOut = false;
let timer = null;
const socket = io();

const SITTING_OUT_STATUS = "You are sitting out. Press “Sit in” to play the next round.";

const $ = id => document.getElementById(id);
function setStatus(text) { $("status").innerText = text; }
function log(text) {
    const line = document.createElement("div");
    line.innerText = text;
    $("log").prepend(line);
}
function renderCards(cards) {
    return cards.map(cardSpan).join("") || "—";
}
function cardSpan(c) {
    return `<span class="card">${c}</span>`;
}
function setBalance(value) {
    balance = value;
    $("balance").innerText = balance.toFixed(2);
}
function setSittingOut(value) {
    sittingOut = value;
    $("sit-toggle").innerText = sittingOut ? "Sit in" : "Sit out";
}

function setPhase(phase, status, { betSeconds = 0, canDouble = true } = {}) {
    stopTimer();
    $("bet-controls").style.display = phase === "betting" ? "inline" : "none";
    $("actions").style.display = phase === "my_turn" ? "inline" : "none";
    // Double down is only legal on the opening two cards.
    $("double-button").style.display = canDouble ? "inline" : "none";
    if (status !== undefined) setStatus(status);
    if (phase === "betting") {
        $("bet-button").disabled = false;
        startBetTimer(betSeconds);
    }
}
function openBetting(seconds) {
    if (sittingOut) setPhase("waiting", SITTING_OUT_STATUS);
    else setPhase("betting", "Place your bet to join this round — or sit it out and stake nothing.",
                  { betSeconds: seconds });
}
function startMyTurn(canDouble = true) {
    highlightTurn(me);
    setPhase("my_turn", "Your turn: hit, stand or double down.", { canDouble });
}

// Actions the player takes (these are what the buttons call)
function sendBet() {
    const amount = parseFloat($("bet-amount").value);
    if (!(amount > 0)) { setStatus("Enter a bet amount greater than 0."); return; }
    if (amount > balance) { setStatus("You can't bet more than your balance."); return; }
    $("bet-button").disabled = true;   // avoid double-submits; re-enabled next round
    socket.emit("bet", { amount });
}
function sendAction(action) {
    socket.emit("player_action", { action });
}

function toggleSit() {
    socket.emit("sit_out", { sitting_out: !sittingOut });
}

function askLeave() {
    $("leave-warning").innerHTML = myBet > 0
        ? `<span class="warn">You have $${myBet} on this hand. Leaving now loses it,
           whatever the cards would have said.</span>
           The rest of your chips reach your balance when this round is over.`
        : "You have nothing staked on this hand.";
    $("leave-modal").classList.add("open");
}
function closeLeave() { $("leave-modal").classList.remove("open"); }

$("leave-button").addEventListener("click", askLeave);
$("stay-button").addEventListener("click", closeLeave);
$("bet-button").addEventListener("click", sendBet);
$("sit-toggle").addEventListener("click", toggleSit);
for (const button of document.querySelectorAll("#actions button")) {
    button.addEventListener("click", () => sendAction(button.dataset.action));
}

socket.on("connect", () => socket.emit("join"));

socket.on("joined", data => {
    setStatus(data.is_player ? `Seated at ${data.table_id}. Waiting for the round to start…`
                             : `Watching ${data.table_id}: a round is in progress, you play the next one.`);
});


socket.on("resumed", data => {
    setBalance(data.balance);
    myBet = data.bet_amount || 0;
    setSittingOut(data.sitting_out);

    if (!data.in_round) {
        setPhase("waiting", sittingOut ? SITTING_OUT_STATUS : "Reconnected. Waiting for the next round…");
        return;
    }
    // The round is in progress: show the current state of the table.
    setDealerCards(data.dealer_cards);
    renderPlayers(data.hands);

    if (data.your_turn) startMyTurn(data.hand.length <= 2);// can double down only on the opening two cards
    else if (data.betting_open && data.bet_amount == null) openBetting(data.bet_seconds_left);
    else setPhase("waiting", data.bet_amount != null ? "Reconnected. Waiting for the round to continue…"
                                                     : "Reconnected: watching this round.");
});

socket.on("game_starting", () => {
    setPhase("waiting", "Round starting…");
    setDealerCards([]);
    $("players-area").innerHTML = "—";
    myBet = 0;
});

socket.on("place_bets", data => openBetting(data.seconds));

socket.on("seat_state", data => {
    setSittingOut(data.sitting_out);
    const status = data.applies_now
        ? (sittingOut ? "Sitting out — the table will not wait for you."
                      : "You are in: betting on the next deal.")
        : (sittingOut ? "You will sit out from the next round; finish this one first."
                      : "You will play again from the next round.");
    if (sittingOut) setPhase("waiting", status);
    else setStatus(status);
});

socket.on("table_idle", () => {
    setPhase("waiting", "Everyone at the table is sitting out. Press “Sit in” to start a round.");
});

socket.on("bet_confirmed", data => {
    log(`${data.user} bet $${data.amount}`);
    if (data.user === me) {
        myBet = data.amount;
        setPhase("waiting", "Bet placed. Waiting for the cards…");
    }
});

// The server may no longer stake balances, so it froze the table
// rather than play rounds central cannot settle. Nobody is kicked.
socket.on("lease_expired", () => {
    $("lease-banner").hidden = false;
    setPhase("waiting", "Paused: waiting for the central server.");
});

socket.on("lease_restored", () => {
    $("lease-banner").hidden = true;
    setStatus("Central server is back — resuming play.");
});

socket.on("no_players_bet", () => {
    setPhase("waiting", "Nobody bet this round. Starting a new betting round…");
});

socket.on("initial_cards", data => {
    renderPlayers(data.hands);
    if (data.dealer_cards) setDealerCards(data.dealer_cards);
    // Action buttons are governed by turn_started, not by the deal.
});

socket.on("turn_started", data => {
    if (data.user === me) {
        startMyTurn();
    } else {
        highlightTurn(data.user);
        setPhase("waiting", `Waiting for ${data.user} to play…`);
    }
});

socket.on("card_drawn", data => {
    log(`${data.user} drew ${data.card}`);
    appendCard(data.user, data.card);
    // After the first hit a hand has 3+ cards, so doubling is no longer legal.
    if (data.user === me) $("double-button").style.display = "none";
});

socket.on("player_busted", data => {
    log(`${data.user} busted!`);
    if (data.user === me) setPhase("waiting", "Busted! Waiting for the round to finish…");
});

socket.on("player_left", data => {
    log(`${data.user} left the table (stake forfeited)`);
});

socket.on("user_stood", data => {
    log(`${data.user} stands`);
    if (data.user === me) setPhase("waiting", "Standing. Waiting for your turn to end…");
});

socket.on("user_doubled", data => {
    log(`${data.user} doubled down and drew ${data.card}`);
    appendCard(data.user, data.card);
    if (data.user === me) setPhase("waiting", "Doubled down. Waiting for the round to finish…");
});

socket.on("player_auto_stand", data => {
    log(`${data.user} took too long: automatic stand`);
    if (data.user === me) setPhase("waiting", "Time's up: automatic stand.");
});

socket.on("dealer_turn", () => {
    clearTurnHighlight();
    setStatus("Dealer's turn — drawing…");
});

socket.on("dealer_card", data => {
    log(`Dealer drew ${data.card}`);
    setDealerCards(data.cards);
});

socket.on("dealer_done", data => {
    clearTurnHighlight();
    setDealerCards(data.cards);
    setStatus("Dealer stands. Settling the round…");
});

socket.on("round_results", data => {
    clearTurnHighlight();
    let myOutcome = null;
    for (const res of data.results) {
        const outcome = res.balance_difference > 0 ? `won $${res.balance_difference}`
                      : res.balance_difference < 0 ? `lost $${-res.balance_difference}`
                      : "pushed (tie)";
        log(`${res.username} ${outcome}`);
        if (res.username === me) {
            setBalance(balance + res.balance_difference);
            myOutcome = outcome;
        }
    }
    myBet = 0;
    setPhase("waiting");
    const base = myOutcome ? `Round over: you ${myOutcome}.` : "Round over.";
    timer = countdown(data.next_round_in || 0,
                      left => setStatus(`${base} Next round in ${left}s…`),
                      () => setStatus(`${base} Next round starting…`));
});

// The buy-in behind this session has been settled, so this page can
// no longer seat us
socket.on("seat_closed", data => {
    setPhase("waiting", data.message);
    setTimeout(() => document.querySelector("#leave-modal form").submit(), 3000);
});

socket.on("error", data => log(`Error: ${data.message}`));

// --- Rendering ---
function appendCard(user, card) {
    const hand = $(`hand-${user}`);
    const span = hand && hand.querySelector(".hand");
    if (!span) return;
    span.innerHTML += cardSpan(card);
    showTotal(span, hand.querySelector(".total"));
}
function renderPlayers(hands) {
    $("players-area").innerHTML = "";
    for (const user in hands) {
        const div = document.createElement("div");
        div.className = "player" + (user === me ? " me" : "");
        
        const name = document.createElement("strong");
        name.textContent = user;
        div.append(name, ": ");
        div.insertAdjacentHTML("beforeend",
            `<span class="hand">${renderCards(hands[user])}</span><span class="total"></span>`);
        div.id = `hand-${user}`;
        $("players-area").appendChild(div);
        showTotal(div.querySelector(".hand"), div.querySelector(".total"));
    }
}
function setDealerCards(cards) {
    $("dealer-cards").innerHTML = renderCards(cards);
    showTotal($("dealer-cards"), $("dealer-total"));
}

function handValue(cards) {
    let total = 0, aces = 0;
    for (const card of cards) {
        const rank = card.slice(0, -1);   // "10♠" -> "10"
        if (rank === "A") { total += 11; aces += 1; }
        else total += ["J", "Q", "K"].includes(rank) ? 10 : Number(rank);
    }
    while (total > 21 && aces) { total -= 10; aces -= 1; }
    return { total, soft: aces > 0 };
}

function totalLabel(total, soft, cardCount) {
    if (cardCount === 0) return "";
    if (total > 21) return `${total} bust`;
    if (total === 21 && cardCount === 2) return "Blackjack";
    return soft ? `soft ${total}` : `${total}`;
}
function showTotal(cardsEl, totalEl) {
    const cards = [...cardsEl.querySelectorAll(".card")].map(el => el.textContent);
    const { total, soft } = handValue(cards);
    totalEl.classList.toggle("bust", total > 21);
    totalEl.innerText = totalLabel(total, soft, cards.length);
}


function highlightTurn(user) {
    clearTurnHighlight();
    const hand = $(`hand-${user}`);
    if (hand) hand.classList.add("turn");
}
function clearTurnHighlight() {
    document.querySelectorAll(".player.turn").forEach(el => el.classList.remove("turn"));
}

// --- Timer ---
// Interval timer with an absolute deadline: 
// updates the UI via render() and calls onEnd() at zero.
function countdown(seconds, render, onEnd) {
    const deadline = Date.now() + seconds * 1000;
    const id = setInterval(tick, 250);
    function tick() {
        const left = Math.ceil((deadline - Date.now()) / 1000);
        if (left > 0) { render(left); return; }
        clearInterval(id);
        onEnd();
    }
    tick();
    return id;
}
function startBetTimer(seconds) {
    if (!(seconds > 0)) return;
    timer = countdown(seconds, left => {
        $("bet-timer").innerText = `${left}s left to bet`;
        $("bet-timer").classList.toggle("urgent", left <= 5);
    }, () => {
        // The server closed the window before our deadline (the message
        // took time to get here): a bet now is refused.
        setPhase("waiting", "Betting closed: you are watching this round.");
    });
}
function stopTimer() {
    clearInterval(timer);
    timer = null;
    $("bet-timer").innerText = "";
    $("bet-timer").classList.remove("urgent");
}
