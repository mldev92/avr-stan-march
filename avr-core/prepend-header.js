const fs = require('fs');
const path = require('path');

const HEADER = "// Copyright (c) " + new Date().getFullYear() + "\n\n";

function walk(dir) {
    const files = fs.readdirSync(dir);
    for (const file of files) {
        const fullPath = path.join(dir, file);
        const stat = fs.statSync(fullPath);
        if (stat.isDirectory()) {
            walk(fullPath);
        } else if (stat.isFile() && fullPath.endsWith('.js')) {
            const content = fs.readFileSync(fullPath, 'utf8');
            if (!content.startsWith("// Copyright") && !content.startsWith(HEADER)) {
                fs.writeFileSync(fullPath, HEADER + content, 'utf8');
                console.log("Patched: ", fullPath);
            }
        }
    }
}

const target = process.argv[2] || 'src';
if (!fs.existsSync(target)) {
    console.log("Target directory not found:", target);
    process.exit(1);
}
walk(target);