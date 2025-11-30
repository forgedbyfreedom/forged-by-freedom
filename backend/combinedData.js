// backend/combinedData.js
import { ok, serverError } from 'wix-http-functions';
import wixData from 'wix-data';

export function get_combinedData(request) {
  return wixData.query("YourDatabaseCollectionName") // Replace with actual collection name
    .find()
    .then(results => ok({ "items": results.items }))
    .catch(err => serverError(err));
}
