import { mediaManager } from 'wix-media-backend';

export async function post_uploadData(request) {
  try {
    const { fileName, fileContent } = await request.body.json();
    const buffer = Buffer.from(fileContent, 'utf-8');

    const uploadResult = await mediaManager.upload(
      '/data',
      buffer,
      fileName,
      { mediaOptions: { mimeType: 'application/json' } }
    );

    return new Response(
      JSON.stringify({ success: true, fileUrl: uploadResult.fileUrl }),
      { headers: { 'Content-Type': 'application/json' } }
    );
  } catch (err) {
    return new Response(
      JSON.stringify({ success: false, error: err.message }),
      { headers: { 'Content-Type': 'application/json' } }
    );
  }
}

// redeploy Sun Nov  9 17:26:14 EST 2025
