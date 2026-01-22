"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.uploadImageToStorage = uploadImageToStorage;
const supabaseService_1 = require("./supabaseService");
async function uploadImageToStorage(buffer, userId) {
    try {
        const filename = `temp/${userId}/${Date.now()}.jpg`;
        const bucketNames = ['temp-images', 'images', 'public'];
        for (const bucket of bucketNames) {
            const { data, error } = await supabaseService_1.supabase.storage
                .from(bucket)
                .upload(filename, buffer, {
                contentType: 'image/jpeg',
                upsert: true
            });
            if (!error) {
                const { data: urlData } = supabaseService_1.supabase.storage
                    .from(bucket)
                    .getPublicUrl(filename);
                let publicUrl = urlData.publicUrl;
                if (publicUrl.startsWith('http://')) {
                    publicUrl = publicUrl.replace('http://', 'https://');
                }
                return publicUrl;
            }
        }
        return null;
    }
    catch (e) {
        console.error('Upload Error:', e);
        return null;
    }
}
