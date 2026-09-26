// Lets the iOS app reach a Katib server on the same network over plain http.
//
// iOS refuses unencrypted connections unless the app says otherwise. NSAllowsLocalNetworking opens
// that door for private addresses only, so a home server works while the open internet still has to
// use https. Run this once after `npm run add:ios`; running it again changes nothing.

import { readFile, writeFile } from 'node:fs/promises';

const PLIST = 'ios/App/App/Info.plist';
const KEY = 'NSAppTransportSecurity';
const BLOCK = `	<key>${KEY}</key>
	<dict>
		<key>NSAllowsLocalNetworking</key>
		<true/>
	</dict>
`;

const plist = await readFile(PLIST, 'utf8');
if (plist.includes(KEY)) {
  console.log(`${PLIST} already allows local networking`);
} else {
  const at = plist.lastIndexOf('</dict>');
  if (at < 0) throw new Error(`${PLIST} does not look like a property list`);
  await writeFile(PLIST, plist.slice(0, at) + BLOCK + plist.slice(at));
  console.log(`added ${KEY} to ${PLIST}`);
}
