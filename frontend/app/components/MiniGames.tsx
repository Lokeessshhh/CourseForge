'use client';

import { useState, useEffect, useCallback } from 'react';
import styles from './MiniGames.module.css';

// Memory Match Game
export function MemoryGame({ compact = false }: { compact?: boolean }) {
  const [cards, setCards] = useState<number[]>([]);
  const [flipped, setFlipped] = useState<number[]>([]);
  const [matched, setMatched] = useState<number[]>([]);
  const [moves, setMoves] = useState(0);
  const [gameWon, setGameWon] = useState(false);

  const initializeGame = useCallback(() => {
    const symbols = [1, 1, 2, 2, 3, 3, 4, 4];
    const shuffled = symbols.sort(() => Math.random() - 0.5);
    setCards(shuffled);
    setFlipped([]);
    setMatched([]);
    setMoves(0);
    setGameWon(false);
  }, []);

  useEffect(() => {
    initializeGame();
  }, [initializeGame]);

  useEffect(() => {
    if (flipped.length === 2) {
      setMoves(m => m + 1);
      const [first, second] = flipped;
      if (cards[first] === cards[second]) {
        setMatched(prev => [...prev, cards[first]]);
        setFlipped([]);
        if (matched.length + 1 >= 4) {
          setGameWon(true);
        }
      } else {
        setTimeout(() => setFlipped([]), 800);
      }
    }
  }, [flipped, cards, matched.length]);

  const handleCardClick = (index: number) => {
    if (flipped.length >= 2 || flipped.includes(index) || matched.includes(cards[index])) return;
    setFlipped(prev => [...prev, index]);
  };

  return (
    <div className={compact ? styles.gameCardCompact : styles.gameCard}>
      <div className={styles.gameHeader}>
        <span className={styles.gameTitle}>MEMORY</span>
        <span className={styles.gameScore}>{moves} moves</span>
      </div>
      <div className={styles.memoryGrid}>
        {cards.map((card, index) => (
          <button
            key={index}
            className={`${styles.memoryCard} ${flipped.includes(index) || matched.includes(card) ? styles.flipped : ''}`}
            onClick={() => handleCardClick(index)}
            disabled={matched.includes(card)}
          >
            <span className={styles.cardSymbol}>
              {flipped.includes(index) || matched.includes(card) ? card : '?'}
            </span>
          </button>
        ))}
      </div>
      {gameWon && (
        <div className={styles.gameWon}>
          <span>WON!</span>
          <button onClick={initializeGame} className={styles.restartBtn}>RESTART</button>
        </div>
      )}
    </div>
  );
}

// Reaction Time Game
export function ReactionGame({ compact = false }: { compact?: boolean }) {
  const [gameState, setGameState] = useState<'waiting' | 'ready' | 'clicked'>('waiting');
  const [startTime, setStartTime] = useState(0);
  const [reactionTime, setReactionTime] = useState<number | null>(null);
  const [bestTime, setBestTime] = useState<number | null>(null);

  const startGame = () => {
    setGameState('waiting');
    setReactionTime(null);
    const delay = Math.random() * 2000 + 1500;
    setTimeout(() => {
      setGameState('ready');
      setStartTime(Date.now());
    }, delay);
  };

  const handleClick = () => {
    if (gameState === 'waiting') {
      setGameState('clicked');
      setReactionTime(null);
    } else if (gameState === 'ready') {
      const time = Date.now() - startTime;
      setReactionTime(time);
      setGameState('clicked');
      if (!bestTime || time < bestTime) {
        setBestTime(time);
      }
    }
  };

  return (
    <div className={compact ? styles.gameCardCompact : styles.gameCard}>
      <div className={styles.gameHeader}>
        <span className={styles.gameTitle}>REACTION</span>
        {bestTime && <span className={styles.gameScore}>Best: {bestTime}ms</span>}
      </div>
      <button
        className={`${styles.reactionBox} ${styles[gameState]}`}
        onClick={handleClick}
        onMouseDown={handleClick}
      >
        {gameState === 'waiting' && 'WAIT...'}
        {gameState === 'ready' && 'CLICK!'}
        {gameState === 'clicked' && reactionTime ? `${reactionTime}ms` : 'TOO EARLY!'}
      </button>
      {gameState === 'clicked' && (
        <button onClick={startGame} className={styles.restartBtn}>TRY AGAIN</button>
      )}
    </div>
  );
}

// Math Challenge Game
export function MathGame({ compact = false }: { compact?: boolean }) {
  const [problem, setProblem] = useState({ a: 0, b: 0, answer: 0 });
  const [userAnswer, setUserAnswer] = useState('');
  const [score, setScore] = useState(0);
  const [feedback, setFeedback] = useState<'correct' | 'wrong' | null>(null);

  const generateProblem = useCallback(() => {
    const a = Math.floor(Math.random() * 10) + 1;
    const b = Math.floor(Math.random() * 10) + 1;
    setProblem({ a, b, answer: a + b });
    setUserAnswer('');
    setFeedback(null);
  }, []);

  useEffect(() => {
    generateProblem();
  }, [generateProblem]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const parsed = parseInt(userAnswer);
    if (parsed === problem.answer) {
      setFeedback('correct');
      setScore(s => s + 1);
      setTimeout(generateProblem, 1000);
    } else {
      setFeedback('wrong');
      setTimeout(() => setFeedback(null), 1000);
    }
  };

  return (
    <div className={compact ? styles.gameCardCompact : styles.gameCard}>
      <div className={styles.gameHeader}>
        <span className={styles.gameTitle}>MATH</span>
        <span className={styles.gameScore}>Score: {score}</span>
      </div>
      <form onSubmit={handleSubmit} className={styles.mathForm}>
        <div className={styles.mathProblem}>
          <span>{problem.a}</span>
          <span>+</span>
          <span>{problem.b}</span>
          <span>=</span>
          <input
            type="number"
            value={userAnswer}
            onChange={(e) => setUserAnswer(e.target.value)}
            className={`${styles.mathInput} ${feedback ? styles[feedback] : ''}`}
            disabled={feedback !== null}
            autoFocus
          />
        </div>
        <button type="submit" className={styles.submitBtn} disabled={!userAnswer}>
          {feedback === 'correct' ? '' : feedback === 'wrong' ? '' : '→'}
        </button>
      </form>
      {feedback && (
        <button onClick={generateProblem} className={styles.restartBtn}>NEXT</button>
      )}
    </div>
  );
}

// Number Guessing Game
export function NumberGuessGame({ compact = false }: { compact?: boolean }) {
  const [target, setTarget] = useState(0);
  const [guess, setGuess] = useState('');
  const [attempts, setAttempts] = useState(0);
  const [hint, setHint] = useState('');
  const [gameWon, setGameWon] = useState(false);

  const initializeGame = useCallback(() => {
    setTarget(Math.floor(Math.random() * 100) + 1);
    setGuess('');
    setAttempts(0);
    setHint('');
    setGameWon(false);
  }, []);

  useEffect(() => {
    initializeGame();
  }, [initializeGame]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const num = parseInt(guess);
    if (!num) return;
    
    setAttempts(a => a + 1);
    if (num === target) {
      setHint(`Correct! ${attempts + 1} attempts`);
      setGameWon(true);
    } else if (num < target) {
      setHint('Higher ↑');
    } else {
      setHint('Lower ↓');
    }
    setGuess('');
  };

  return (
    <div className={compact ? styles.gameCardCompact : styles.gameCard}>
      <div className={styles.gameHeader}>
        <span className={styles.gameTitle}>GUESS</span>
        <span className={styles.gameScore}>{attempts} tries</span>
      </div>
      <form onSubmit={handleSubmit} className={styles.guessForm}>
        <input
          type="number"
          value={guess}
          onChange={(e) => setGuess(e.target.value)}
          className={styles.guessInput}
          placeholder="1-100"
          disabled={gameWon}
          autoFocus
        />
        <button type="submit" className={styles.submitBtn} disabled={!guess || gameWon}>
          GUESS
        </button>
      </form>
      {hint && (
        <div className={`${styles.guessHint} ${gameWon ? styles.correct : ''}`}>
          {hint}
        </div>
      )}
      {gameWon && (
        <button onClick={initializeGame} className={styles.restartBtn}>PLAY AGAIN</button>
      )}
    </div>
  );
}

// Click Speed Game
export function ClickSpeedGame({ compact = false }: { compact?: boolean }) {
  const [clicks, setClicks] = useState(0);
  const [timeLeft, setTimeLeft] = useState(0);
  const [gameActive, setGameActive] = useState(false);
  const [bestCPS, setBestCPS] = useState(0);

  const startGame = () => {
    setClicks(0);
    setTimeLeft(10);
    setGameActive(true);
  };

  useEffect(() => {
    if (timeLeft > 0) {
      const timer = setTimeout(() => setTimeLeft(t => t - 1), 1000);
      return () => clearTimeout(timer);
    } else if (gameActive) {
      setGameActive(false);
      const cps = clicks / 10;
      if (cps > bestCPS) setBestCPS(cps);
    }
  }, [timeLeft, gameActive, clicks, bestCPS]);

  const handleClick = () => {
    if (gameActive) {
      setClicks(c => c + 1);
    }
  };

  return (
    <div className={compact ? styles.gameCardCompact : styles.gameCard}>
      <div className={styles.gameHeader}>
        <span className={styles.gameTitle}>CLICK SPEED</span>
        {bestCPS > 0 && <span className={styles.gameScore}>Best: {bestCPS}/s</span>}
      </div>
      <button
        className={`${styles.clickBox} ${gameActive ? styles.active : ''}`}
        onClick={handleClick}
        disabled={!gameActive && timeLeft === 0}
      >
        {timeLeft > 0 ? `${timeLeft}s` : gameActive ? 'CLICK!' : `${clicks} clicks`}
      </button>
      {!gameActive && (
        <button onClick={startGame} className={styles.restartBtn}>
          {timeLeft === 0 ? 'START (10s)' : 'RESTART'}
        </button>
      )}
    </div>
  );
}
