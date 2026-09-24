import { describe, expect, it } from 'vitest';
import { Viewport, ZOOM_STEPS } from './viewport';

function make(): Viewport {
  return new Viewport(1000, 600, 2000, 1000);
}

describe('Viewport', () => {
  it('fits the image with padding and centers it', () => {
    const vp = make();
    vp.fit(32);
    expect(vp.scale).toBeCloseTo(Math.min(936 / 2000, 536 / 1000));
    const topLeft = vp.imageToScreen({ x: 0, y: 0 });
    const bottomRight = vp.imageToScreen({ x: 2000, y: 1000 });
    expect(topLeft.x + bottomRight.x).toBeCloseTo(1000);
    expect(topLeft.y + bottomRight.y).toBeCloseTo(600);
  });

  it('converts screen to image and back', () => {
    const vp = make();
    vp.fit();
    const p = { x: 400, y: 250 };
    const back = vp.imageToScreen(vp.screenToImage(p));
    expect(back.x).toBeCloseTo(p.x);
    expect(back.y).toBeCloseTo(p.y);
  });

  it('maps normalized coordinates through the image size', () => {
    const vp = make();
    vp.scale = 1;
    vp.offsetX = 10;
    vp.offsetY = 20;
    expect(vp.normToScreen({ x: 0.5, y: 0.5 })).toEqual({ x: 1010, y: 520 });
    expect(vp.screenToNorm({ x: 1010, y: 520 })).toEqual({ x: 0.5, y: 0.5 });
  });

  it('keeps the anchor point fixed while zooming', () => {
    const vp = make();
    vp.fit();
    const anchor = { x: 300, y: 200 };
    const before = vp.screenToImage(anchor);
    vp.zoomBy(2, anchor);
    const after = vp.screenToImage(anchor);
    expect(after.x).toBeCloseTo(before.x);
    expect(after.y).toBeCloseTo(before.y);
  });

  it('steps through the preset zoom levels', () => {
    const vp = make();
    vp.scale = 1;
    vp.zoomStep(1);
    expect(vp.scale).toBeCloseTo(1.25);
    vp.zoomStep(-1);
    vp.zoomStep(-1);
    expect(vp.scale).toBeCloseTo(0.75);
    vp.scale = ZOOM_STEPS[ZOOM_STEPS.length - 1] as number;
    vp.zoomStep(1);
    expect(vp.scale).toBe(8);
  });

  it('clamps extreme zoom', () => {
    const vp = make();
    vp.zoomBy(1e9);
    expect(vp.scale).toBe(32);
    vp.zoomBy(1e-9);
    expect(vp.scale).toBe(0.02);
  });

  it('does nothing when there is no image yet', () => {
    const vp = new Viewport(500, 500, 0, 0);
    vp.fit();
    expect(vp.scale).toBe(1);
  });
});
