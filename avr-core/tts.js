const axios = require('axios');
const EventEmitter = require('events');
const logger = require('./logger');

class Tts extends EventEmitter {
    constructor() {
        super();
        this.textQueue = [];
        this.isSendingText = false;
    }

    async addToQueue(text) {
        this.textQueue.push(text);
        this.processTextQueue();
    }

    async processTextQueue() {
        if (this.isSendingText || this.textQueue.length === 0) {
            return;
        }
        
        this.isSendingText = true;
        const text = this.textQueue.shift();
        const audioChunks = [];
        
        try {
            const requestData = {
                text: text
            };
            
            const response = await axios({
                method: 'POST',
                url: process.env.TTS_SERVICE_URL || 'http://tts-service/generate',
                data: requestData,
                responseType: 'stream'
            });
            
            response.data.on('data', (chunk) => {
                audioChunks.push(chunk);
            });
            
            response.data.on('end', () => {
                const audioBuffer = Buffer.concat(audioChunks);
                this.emit('audio', audioBuffer);
                logger.info('Received TTS audio stream', audioBuffer.length, 'bytes');
                this.emit('end');
                this.isSendingText = false;
                this.processTextQueue();
            });
            
            response.data.on('error', (error) => {
                logger.error('Error during TTS streaming: ' + error);
                this.emit('error', error);
                this.isSendingText = false;
                this.processTextQueue();
            });
            
        } catch (error) {
            logger.error('Error calling TTS service: ' + error.message);
            this.emit('error', error);
            this.isSendingText = false;
            this.processTextQueue();
        }
    }

    clearQueue() {
        this.textQueue = [];
        this.isSendingText = false;
    }
}

module.exports = { Tts };