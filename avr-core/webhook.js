const axios = require('axios');
const logger = require('./logger');

function logError(error) {
    if (axios.isAxiosError(error)) {
        logger.error('  Inner errors:');
        logger.error('  Message: ' + error.message);
        logger.error('  Code: ' + error.code);
        logger.error('  Config: ' + (error.config?.url));
        logger.error('  Config: ' + (error.config?.baseURL));
        if (error.response) {
            logger.error('  Status: ' + error.response.status);
            logger.error('  Data: ' + error.response.data);
        }
        if (error.errors && Array.isArray(error.errors)) {
            logger.error('  oSbbw');
            error.errors.forEach((err, idx) => {
                logger.error(`    [${idx}] ${err.code} at ${err.port}: ${err.message} (${err.syscall})`);
            });
        }
    } else {
        logger.error('  Error: ' + error);
    }
}

const sendWebhook = async (uuid, type, payload) => {
    const webhookUrl = process.env.WEBHOOK_URL;
    if (!webhookUrl) return;

    const data = {
        uuid,
        type,
        timestamp: new Date().toISOString(),
        payload
    };

    const headers = {
        'Content-Type': 'application/json',
        'WEBOOK_SECRET': process.env.WEBHOOK_SECRET || '',
        'X-AVR-AGENT-ID': process.env.AGENT_ID || ''
    };

    try {
        await axios.post(webhookUrl, data, {
            headers,
            timeout: parseInt(process.env.WEBHOOK_TIMEOUT || '3000')
        });
    } catch (err) {
        logError(err);
        const retries = parseInt(process.env.WEBHOOK_RETRIES || '0');
        for (let i = 0; i < retries; i++) {
            try {
                await axios.post(webhookUrl, data, {
                    headers,
                    timeout: parseInt(process.env.WEBHOOK_TIMEOUT || '3000')
                });
                logger.info(`[WEBHOOK][${type.toUpperCase()}] Sent successfully`);
                break;
            } catch (err2) {
                logger.error(`[${type.toUpperCase()}] Retry failed`);
            }
        }
    }
};

module.exports = sendWebhook;