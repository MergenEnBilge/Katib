# Class tools and dataset health

## Changing classes safely

Open **Manage classes** to work with all of a project's classes in one place.

- **Rename** changes the class everywhere at once. Katib remembers the old name, so importing a label file that still uses it lands in the right class.
- **Recolor** and **reorder** change only how the class looks and where it sits in exports.
- **Merge into...** relabels every shape of one class as another, then removes the first class.
- **Delete...** removes a class together with all of its shapes.
- **Attributes** add extra fields to a class, such as "occluded" (yes or no) or "size" (small, medium, large). Removing an attribute keeps the values already stored, and they return if you add it back.

### Preview first, undo later

Merging and deleting always show what they will touch before you confirm. For example, "212 annotations on 87 images will be relabeled". Deleting a class asks you to type its name.

Every bulk change is written to the history with a summary. Open the history to undo one, including after you have closed the browser. Undo is kept for 30 days by default (`limits.operation_retention_days`). Shapes you edited after the change are left alone and counted, so undo never overwrites newer work.

## The class gallery

The class gallery shows a crop of every shape in one class, side by side. Use it to spot mistakes by eye: the one truck in a page of buses stands out at once.

Select shapes in the gallery to relabel or delete them in bulk. Filters narrow the view to one class, to images with a certain status, or to tiny shapes only.

## Dataset health

**Dataset health** looks for problems before you train:

| Finding | What it means |
|---------|---------------|
| Tiny shapes | Shapes only a few pixels wide, usually a stray click |
| Duplicate shapes | Two shapes of one class on one image that overlap almost exactly |
| Near-identical photos | Different files that look the same, for example frames from a video |
| Empty images | Images with no shapes, which is fine for negatives and a mistake otherwise |
| Class balance | Classes with far fewer examples than the biggest one |

Each finding links to the shapes or images concerned, so you can fix them straight away.
