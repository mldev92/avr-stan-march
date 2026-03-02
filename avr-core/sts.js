const axios = require('axios');
const { PassThrough } = require('stream');
const EventEmitter = require('events');
const logger = require('./logger');

class Sts extends EventEmitter {
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
                url: process.env.STREAM_URL || 'external_service_url',
                headers: {
                    'Content-Type': 'application/octet-stream',
                    'Transfer-Encoding': 'chunked',
                    'X-UUID': uuid
                },
                data: this.stream,
                responseType: 'stream'
            });

            this.responseStream = response.data;
            
            this.responseStream.on('data', (chunk) => {
                this.emit('data', chunk);
            });

            this.responseStream.on('end', () => {
                logger.info('Streaming complete');
                this.emit('end');
            });

            this.responseStream.on('error', (error) => {
                logger.error('Error during external service streaming: ' + error);
                this.emit('error', error);
            });
            
        } catch (error) {
            logger.error('Error starting stream: ' + error.message);
            this.emit('error', error);
        }
    }

    async sendData(uuid, data) {
        if (!this.stream) {
            await this.startStreaming(uuid);
        }
        
        if (this.stream) {
            this.stream.write(data);
        } else {
            logger.error('Error: Stream not available');
            this.emit('error', new Error('Stream not available'));
        }
    }

    stopStreaming() {
        if (this.stream) {
            this.stream.end();
            this.stream = null;
            logger.info('Streaming stopped');
        }
    }
}

module.exports = { Sts };