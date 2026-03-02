function extractUUID(inputString) {
    // Regular expression to match UUID
    const uuidPattern = /[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}/;

    // Use match() to find the UUID in the string
    const match = inputString.match(uuidPattern);

    // Return the matched UUID if found, otherwise return null
    return match ? match[0] : null;
}

function findCallByUUID(obj, uuid) {
    // Iterate over the keys of the object
    for (const key in obj) {
        // Check if the uuid matches the uuid in the current object
        if (obj[key].uuid === uuid) {
            return obj[key];  // Return the matching object
        }
    }
    return null;  // Return null if no match is found
}

module.exports = {
    extractUUID,
    findCallByUUID
};