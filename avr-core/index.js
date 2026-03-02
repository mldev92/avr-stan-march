const net = require('net');
const { ClientHandler } = require('./socket');
const logger = require('./logger');

function calculateDurationInSeconds(startTime) {
    return ((performance.now() - startTime) / 1000).toFixed(2);
}

const server = net.createServer(socket => {
    logger.info('Client connected');
    const startTime = performance.now();
    const clientHandler = new ClientHandler(socket);
    
    clientHandler.on('close', () => {
        logger.log('Client disconnected. Duration: ' + calculateDurationInSeconds(startTime) + ' seconds');
    });
    
    clientHandler.on('error', error => {
        logger.error('Client error: ' + error);
        logger.log('Client disconnected. Duration: ' + calculateDurationInSeconds(startTime) + ' seconds');
    });
});

const port = process.env.PORT || 5001;

server.listen(port, () => {
    logger.log('Server listening on port ' + port);
    
    if (process.env.STS_URL) {
        logger.log('STS URL: ' + process.env.STS_URL);
    } else {
        logger.log('No STS URL provided');
    }
    
    if (process.env.TENANT_ID) {
        logger.log('Tenant ID: ' + process.env.TENANT_ID);
    } else {
        logger.log('No tenant ID provided');
    }
    
    if (process.env.CLIENT_ID) {
        logger.log('Client ID: ' + process.env.CLIENT_ID);
    } else {
        logger.log('No client ID provided');
    }
    
    if (process.env.CLIENT_SECRET) {
        logger.log('Client secret is set');
    } else {
        logger.log('No client secret provided');
    }
});

server.on('error', error => {
    logger.error('Server error: ' + error);
});