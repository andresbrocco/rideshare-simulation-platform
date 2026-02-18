/**
 * Simple browser logger with level filtering and optional JSON output.
 */

type LogLevel = 'debug' | 'info' | 'warn' | 'error';

const LOG_LEVELS: Record<LogLevel, number> = {
  debug: 0,
  info: 1,
  warn: 2,
  error: 3,
};

class Logger {
  private level: LogLevel;
  private jsonOutput: boolean;

  constructor() {
    this.level = (import.meta.env.VITE_LOG_LEVEL as LogLevel) || 'info';
    this.jsonOutput = import.meta.env.PROD;
  }

  private shouldLog(level: LogLevel): boolean {
    return LOG_LEVELS[level] >= LOG_LEVELS[this.level];
  }

  private formatMessage(
    level: LogLevel,
    message: string,
    extra?: Record<string, unknown>
  ): string | object {
    if (this.jsonOutput) {
      return {
        timestamp: new Date().toISOString(),
        level,
        message,
        ...extra,
      };
    }
    const extraStr = extra ? ` ${JSON.stringify(extra)}` : '';
    return `[${level.toUpperCase()}] ${message}${extraStr}`;
  }

  debug(message: string, extra?: Record<string, unknown>): void {
    if (this.shouldLog('debug')) {
      console.debug(this.formatMessage('debug', message, extra));
    }
  }

  info(message: string, extra?: Record<string, unknown>): void {
    if (this.shouldLog('info')) {
      console.info(this.formatMessage('info', message, extra));
    }
  }

  warn(message: string, extra?: Record<string, unknown>): void {
    if (this.shouldLog('warn')) {
      console.warn(this.formatMessage('warn', message, extra));
    }
  }

  error(message: string, extra?: Record<string, unknown>): void {
    if (this.shouldLog('error')) {
      console.error(this.formatMessage('error', message, extra));
    }
  }
}

export const logger = new Logger();
