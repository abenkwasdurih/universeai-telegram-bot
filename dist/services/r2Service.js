"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.uploadVideoToR2 = uploadVideoToR2;
const client_s3_1 = require("@aws-sdk/client-s3");
const config_1 = require("../config");
const axios_1 = __importDefault(require("axios"));
const s3Client = new client_s3_1.S3Client({
    region: 'auto',
    endpoint: `https://${config_1.config.r2.accountId}.r2.cloudflarestorage.com`,
    credentials: {
        accessKeyId: config_1.config.r2.accessKeyId,
        secretAccessKey: config_1.config.r2.secretAccessKey,
    },
});
async function uploadVideoToR2(videoUrl, fileName, userId) {
    try {
        // Download video
        const response = await axios_1.default.get(videoUrl, { responseType: 'arraybuffer' });
        const buffer = Buffer.from(response.data);
        const key = `videos/${userId}/${fileName}.mp4`;
        await s3Client.send(new client_s3_1.PutObjectCommand({
            Bucket: config_1.config.r2.bucketName,
            Key: key,
            Body: buffer,
            ContentType: 'video/mp4',
        }));
        // Return Public URL
        return `${config_1.config.r2.publicUrl}/${key}`;
    }
    catch (e) {
        console.error('R2 Upload Error:', e);
        return null;
    }
}
