import { S3Client, PutObjectCommand } from '@aws-sdk/client-s3';
import { config } from '../config';
import axios from 'axios';

const s3Client = new S3Client({
    region: 'auto',
    endpoint: `https://${config.r2.accountId}.r2.cloudflarestorage.com`,
    credentials: {
        accessKeyId: config.r2.accessKeyId,
        secretAccessKey: config.r2.secretAccessKey,
    },
});

export async function uploadVideoToR2(videoUrl: string, fileName: string, userId: string): Promise<string | null> {
    try {
        // Download video
        const response = await axios.get(videoUrl, { responseType: 'arraybuffer' });
        const buffer = Buffer.from(response.data);

        const key = `videos/${userId}/${fileName}.mp4`;

        await s3Client.send(new PutObjectCommand({
            Bucket: config.r2.bucketName,
            Key: key,
            Body: buffer,
            ContentType: 'video/mp4',
        }));

        // Return Public URL
        return `${config.r2.publicUrl}/${key}`;
    } catch (e) {
        console.error('R2 Upload Error:', e);
        return null;
    }
}
