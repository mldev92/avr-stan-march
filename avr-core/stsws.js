require('dotenv').config();
const EventEmitter = require('events');
const WebSocket = require('ws');
const logger = require('./logger');

class StsWs extends EventEmitter {
  constructor() {
    super();
    this.ws = null;
  }

  async startStreaming(streamId) {
    logger.info('[STS] startStreaming: ' + streamId);

    try {
      const wsUrl = process.env.STS_URL;
      if (!wsUrl) {
        throw new Error('STS_URL environment variable is not set');
      }

      logger.info('[STS] Connecting to: ' + wsUrl);
      this.ws = new WebSocket(wsUrl);

      this.ws.on('open', () => {
        logger.info('[STS] WebSocket opened');
        const msg = {
          type: 'init',
          streamId: streamId
        };
        this.ws.send(JSON.stringify(msg));
      });

      this.ws.on('message', (data) => {
        try {
          const msg = JSON.parse(data.toString());
          switch (msg.type) {
            case 'init':
              this.emit('init');
              break;
            case 'role':
              logger.info(`[STS] role: ${msg.role}, text: ${msg.text}`);
              if (msg.role && msg.text) {
                this.emit('role', msg);
              }
              break;
            case 'audio':
              this.emit('audio', Buffer.from(msg.audio, 'base64'));
              break;
            case 'error':
              this.emit('error', msg.error);
              break;
            default:
              logger.warn('[STS] Unknown message type: ' + msg.type);
              break;
          }
        } catch (err) {
          logger.error('[STS] Error parsing message: ' + err);
          this.emit('error', err);
        }
      });

      this.ws.on('error', (err) => {
        logger.error('STS WebSocket error: ' + err);
        this.emit('error', err);
      });

      this.ws.on('close', (code, reason) => {
        logger.info('STS WebSocket closed: ' + code + ' ' + reason.toString());
        this.emit('close');
      });

    } catch (err) {
      logger.error('[STS] startStreaming error', err);
      this.emit('error', err);
      throw err;
    }
  }

  async sendAudio(streamId, audioBuffer) {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify({
        type: 'audio',
        audio: audioBuffer.toString('base64')
      }));
    } else {
      logger.error('[STS] WebSocket is not open');
      this.emit('error', new Error('WebSocket is not open'));
    }
  }

  processDtmfDigit(digit) {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify({
        type: 'dtmf_digit',
        digit: digit
      }));
    }
  }

  stopStreaming() {
    logger.info('[STS] stopStreaming');
    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }
  }
}

module.exports = { StsWs };