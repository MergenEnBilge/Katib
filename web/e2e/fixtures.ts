import type { Page } from '@playwright/test';
import { mkdirSync, rmSync, writeFileSync } from 'node:fs';
import { join, resolve } from 'node:path';
import { crc32, deflateSync } from 'node:zlib';

export const ROOT = resolve(import.meta.dirname, '..', '.e2e');
export const DATA_DIR = join(ROOT, 'data');
export const TEAM_DATA_DIR = join(ROOT, 'team-data');
export const LIBRARY = join(ROOT, 'library');
//: A small YOLO-shaped dataset, nested under its own folder the way a real one would be, so a
//: test can pick "the folder" the way a browser's folder picker actually hands files back.
export const UPLOAD_SET = join(ROOT, 'upload-set');
//: The same dataset's files, as individual paths -- for picking them loose, with no folder
//: involved, the way a flat multi-file picker hands files back.
export const UPLOAD_SET_YAML = join(UPLOAD_SET, 'data.yaml');
export const UPLOAD_SET_IMAGE = join(UPLOAD_SET, 'images', 'a.png');
export const UPLOAD_SET_LABEL = join(UPLOAD_SET, 'labels', 'a.txt');

function chunk(type: string, data: Buffer): Buffer {
  const body = Buffer.concat([Buffer.from(type), data]);
  const out = Buffer.alloc(body.length + 8);
  out.writeUInt32BE(data.length, 0);
  body.copy(out, 4);
  out.writeUInt32BE(crc32(body), body.length + 4);
  return out;
}

/** A solid-color PNG with a lighter square in the middle, enough to see on the canvas. */
export function png(width: number, height: number, rgb: [number, number, number]): Buffer {
  const row = 1 + width * 3;
  const raw = Buffer.alloc(row * height);
  for (let y = 0; y < height; y++) {
    for (let x = 0; x < width; x++) {
      const inside = Math.abs(x - width / 2) < width / 6 && Math.abs(y - height / 2) < height / 6;
      const o = y * row + 1 + x * 3;
      for (let c = 0; c < 3; c++) raw[o + c] = inside ? 235 : (rgb[c] as number);
    }
  }
  const header = Buffer.alloc(13);
  header.writeUInt32BE(width, 0);
  header.writeUInt32BE(height, 4);
  header[8] = 8;
  header[9] = 2;
  return Buffer.concat([
    Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]),
    chunk('IHDR', header),
    chunk('IDAT', deflateSync(raw)),
    chunk('IEND', Buffer.alloc(0)),
  ]);
}

/** Fresh data directory and a small image library. Runs once, in the main Playwright process. */
export function prepare(): void {
  rmSync(ROOT, { recursive: true, force: true });
  mkdirSync(LIBRARY, { recursive: true });
  mkdirSync(DATA_DIR, { recursive: true });
  mkdirSync(TEAM_DATA_DIR, { recursive: true });
  const colors: [number, number, number][] = [
    [40, 60, 90],
    [70, 40, 60],
    [30, 80, 60],
  ];
  colors.forEach((rgb, i) => writeFileSync(join(LIBRARY, `street${i + 1}.png`), png(600, 400, rgb)));

  mkdirSync(join(UPLOAD_SET, 'images'), { recursive: true });
  mkdirSync(join(UPLOAD_SET, 'labels'), { recursive: true });
  writeFileSync(join(UPLOAD_SET, 'data.yaml'), 'path: .\ntrain: images\nval: images\nnames:\n  0: car\n');
  writeFileSync(join(UPLOAD_SET, 'labels', 'a.txt'), '0 0.5 0.5 0.2 0.2\n');
  writeFileSync(join(UPLOAD_SET, 'images', 'a.png'), png(64, 64, [90, 40, 60]));
}

/** In the open Import dialog, connect the test library by typing its path. */
export async function connectLibrary(page: Page): Promise<void> {
  await page.getByText('Type a folder path instead').click();
  await page.getByLabel('Folder on the Katib computer').fill(LIBRARY);
  await page.getByRole('button', { name: 'Connect', exact: true }).click();
}
