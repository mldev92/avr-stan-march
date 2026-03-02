const { RealTimeVAD } = require('@ricky0123/vad-node');
const { EventEmitter } = require('events');
const logger = require('./logger');

const FRAME_SIZE = 512;

class VAD extends EventEmitter {
    vad;
    onSpeechEnd;
    audioBuffer;
    bufferIndex = 0;
    frameCount = 0;
    speechProbabilities = [];

    constructor() {
        super();
        this.audioBuffer = new Float32Array(FRAME_SIZE);
        this.bufferIndex = 0;
    }

    async initialize() {
        this.vad = await RealTimeVAD.new({
            positiveSpeechThreshold: process.env.VAD_POSITIVE_SPEECH_THRESHOLD || 0.08,
            negativeSpeechThreshold: process.env.VAD_NEGATIVE_SPEECH_THRESHOLD || 0.03,
            minSpeechFrames: process.env.VAD_MIN_SPEECH_FRAMES || 3,
            preSpeechPadFrames: process.env.VAD_PRE_SPEECH_PAD_FRAMES || 3,
            redemptionFrames: process.env.VAD_REDEMPTION_FRAMES || 8,
            frameSamples: process.env.VAD_FRAME_SAMPLES || 512,
            sampleRate: 8000,
            model: process.env.VAD_MODEL || 'v5',
            
            onFrameProcessed: (result, frame) => {
                this.frameCount++;
                const isSpeech = result.probability >= 0.08;
                this.speechProbabilities.push(result.probability);
                
                if (this.speechProbabilities.length > 20) {
                    this.speechProbabilities.shift();
                }
                
                logger.debug(`Frame ${this.frameCount} - isSpeech: ${isSpeech.toString().substring(0, 4)} - prob: ${result.probability}`);
                
                if (this.frameCount > 50) {
                    const avgProbability = this.speechProbabilities.reduce((sum, prob) => sum + prob, 0) / this.speechProbabilities.length;
                    if (avgProbability < 0.001) {
                        logger.debug('⚠️  Detected model corruption - resetting');
                        this.reset();
                    }
                }
            },
            
            onSpeechStart: () => {
                // Empty implementation
            },
            
            onSpeechRealStart: () => {
                this.speechProbabilities.shift();
                this.emit('speechStart');
            },
            
            onSpeechEnd: (audioData) => {
                this.emit('speechEnd', audioData);
            }
        });
        
        this.vad.start();
    }

    async processAudio(audioData) {
        const audioSamples = new Int16Array(new Uint8Array(audioData).buffer);
        let samplesProcessed = 0;
        
        while (samplesProcessed < audioSamples.length) {
            const remainingBufferSpace = FRAME_SIZE - this.bufferIndex;
            const remainingSamples = audioSamples.length - samplesProcessed;
            const samplesToCopy = Math.min(remainingBufferSpace, remainingSamples);
            
            for (let i = 0; i < samplesToCopy; i++) {
                const sample = audioSamples[samplesProcessed + i] / 32768;
                this.audioBuffer[this.bufferIndex + i] = sample;
            }
            
            this.bufferIndex += samplesToCopy;
            samplesProcessed += samplesToCopy;
            
            if (this.bufferIndex === FRAME_SIZE) {
                try {
                    await this.vad.processAudio(this.audioBuffer);
                } catch (error) {
                    logger.error('Error processing frame:', error);
                }
                
                this.audioBuffer = new Float32Array(FRAME_SIZE);
                this.bufferIndex = 0;
            }
        }
    }

    async reset() {
        try {
            if (this.vad) {
                this.vad.reset();
                this.frameCount = 0;
                this.speechProbabilities = [];
            }
        } catch (error) {
            logger.error('Error resetting VAD:', error);
        }
    }

    async stop() {
        if (this.vad) {
            await this.vad.pause();
            this.vad.stop();
        }
    }
}

module.exports = { VAD };