require('dotenv').config();
const axios = require('axios');
const { PassThrough } = require('stream');
const EventEmitter = require('events');
const logger = require('./logger');

class Asr extends EventEmitter {
    constructor() {
        super();
        this.stream = null;
        this.responseStream = null;
    }

    async startStreaming(uuid) {
        this.stream = new PassThrough();
        
        try {
            const response = await axios({
                method: 'POST',
                url: process.env.ASR_URL || 'http://localhost:3000/stream',
                headers: {
                    'Content-Type': 'audio/wav',
                    'Transfer-Encoding': 'chunked',
                    'X-UUID': uuid
                },
                data: this.stream,
                responseType: 'stream'
            });

            this.responseStream = response.data;
            
            this.responseStream.on('data', (chunk) => {
                const text = chunk.toString();
                logger.info('Received ASR result: ' + text);
                this.emit('transcript', text);
            });

            this.responseStream.on('end', () => {
                this.stream.end();
                this.stream = null;
                logger.info('Streaming stopped');
            });

            this.responseStream.on('error', (error) => {
                logger.error('Stream error: ' + error);
                this.emit('error', error);
            });

        } catch (error) {
            logger.error('ASR request failed: ' + error.message);
            this.emit('error', error);
        }
    }

    async sendAudio(uuid, audioData) {
        if (!this.stream) {
            await this.startStreaming(uuid);
        } else {
            this.stream.write(audioData);
        }
    }

    stopStreaming() {
        if (this.stream) {
            this.stream.end();
            this.stream = null;
            logger.info('ASR streaming stopped');
        }
    }
}

module.exports = { Asr };