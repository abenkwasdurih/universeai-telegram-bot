import { supabase } from './supabaseService';

export async function uploadImageToStorage(buffer: Buffer, userId: string): Promise<string | null> {
    try {
        const filename = `temp/${userId}/${Date.now()}.jpg`;
        const bucketNames = ['temp-images', 'images', 'public'];

        for (const bucket of bucketNames) {
            const { data, error } = await supabase.storage
                .from(bucket)
                .upload(filename, buffer, {
                    contentType: 'image/jpeg',
                    upsert: true
                });

            if (!error) {
                const { data: urlData } = supabase.storage
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
    } catch (e) {
        console.error('Upload Error:', e);
        return null;
    }
}
