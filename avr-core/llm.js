const axios = require('axios');
const EventEmitter = require('events');
const logger = require('./logger');

class Llm extends EventEmitter {
    constructor() {
        super();
        this.accumulatedContent = '';
    }

    async sendToLlm(message, context, options) {
        try {
            const requestData = {
                message: message,
                context: context,
                options: options
            };

            const response = await axios({
                method: 'POST',
                url: process.env.LLM_SERVICE_URL || 'http://localhost:3000/api/llm',
                headers: {
                    'Content-Type': 'application/json'
                },
                data: requestData,
                responseType: 'stream'
            });

            response.data.on('data', (chunk) => {
                const dataString = chunk.toString();
                logger.info('Received data from LLM service: ' + dataString);
                
                try {
                    const parsedData = JSON.parse(dataString);
                    
                    if (parsedData.type === 'text') {
                        this.handleText(parsedData.content);
                    } else if (parsedData.type === 'audio') {
                        this.handleAudio(parsedData.content);
                    } else {
                        logger.warn('Unknown data type from LLM: ' + parsedData.type);
                    }
                } catch (error) {
                    logger.warn('Error parsing LLM response: ' + error);
                    this.emit('error', error);
                }
            });

            response.data.on('end', () => {
                logger.info('LLM stream ended');
                if (this.accumulatedContent) {
                    const cleanedText = this.cleanText(this.accumulatedContent);
                    logger.info('Processing final accumulated content');
                    this.emitCompleteSentences(cleanedText);
                    this.accumulatedContent = '';
                }
                this.emit('end');
            });

            response.data.on('error', (error) => {
                logger.error('Stream error: ' + error);
                this.emit('error', error);
            });

        } catch (error) {
            logger.error('Error sending to LLM: ' + error.message);
            this.emit('error', error);
        }
    }

    handleText(textContent) {
        logger.info('Handling text content: ' + textContent);
        this.accumulatedContent += textContent;
        
        let cleanedText = this.accumulatedContent.replace(/【.*?】/g, '');
        const sentences = cleanedText.match(/[^.!?]*[.!?]/g);
        
        if (sentences) {
            sentences.forEach(sentence => {
                const cleanedSentence = this.cleanText(sentence);
                logger.info('Cleaned text content: ' + cleanedSentence);
                this.emit('text', cleanedSentence);
            });
            
            const remainingChars = sentences.join('').length;
            let remainingText = this.accumulatedContent;
            remainingText = remainingText.replace(/【.*?】/g, '');
            remainingText = remainingText.replace(/[^.!?]*[.!?]/g, '');
            this.accumulatedContent = remainingText;
        }
    }

    emitCompleteSentences(text) {
        const config = { type: 'text' };
        const sentences = text.match(/[^.!?]*[.!?]/g);
        
        sentences && sentences.forEach(sentence => {
            logger.info('Emitting complete sentence: ' + sentence);
            this.emit(config.type, sentence);
        });
    }

    handleAudio(audioContent) {
        const config = { type: 'audio' };
        logger.info('Handling audio content: ' + audioContent);
        this.emit(config.type, audioContent);
    }

    cleanText(text) {
        return text
            .replace(/[^\p{L}\p{N}\p{P}\p{Z}\p{M}\s]/gu, '')
            .replace(/\*+/g, '')
            .replace(/\n+/g, ' ')
            .replace(/#+/g, '')
            .trim();
    }
}

module.exports = { Llm };