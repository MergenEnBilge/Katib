# Classes and dataset health

This guide covers how to rename, merge and remove classes safely, how to review every shape in a class,
and how to check a dataset before you train on it.

## Managing classes

Open **Manage classes** to work with all of a project's classes in one place.

- **Rename** changes the class name everywhere at once. Katib remembers the old name too, so a label
  file that still uses it goes into the right class when you import it.
- **Recolour** and **reorder** change how a class looks, and the order it appears in exports.
- **Merge into** turns every shape of one class into another class, then removes the first class.
- **Delete** removes a class and all of its shapes.
- **Attributes** add extra fields to a class, such as "occluded" (yes or no) or "size" (small, medium
  or large). If you remove an attribute, its values are kept. They come back if you add the attribute
  again.

### You see the effect before you confirm

Merging and deleting always show what they will change before they run. For example: "212 shapes on 87
pictures will be relabelled." Deleting a class also asks you to type its name.

Every bulk change is recorded in **History**, with a summary. You can undo it there, even after you
close the browser. Undo is kept for 30 days by default. You can change that with
`limits.operation_retention_days`.

Shapes you edited after the change are left as they are, and Katib tells you how many. Undo never
overwrites newer work.

## The class gallery

The gallery shows a cropped picture of every shape in one class, side by side. It makes mistakes easy
to spot. A single truck in a page of buses stands out straight away.

Select shapes in the gallery to change or delete them in bulk. Filters narrow the view to one class,
to pictures with a certain status, or to tiny shapes only.

## Dataset health

**Dataset health** checks your labels before you train:

| What it finds | What it means |
|---------------|---------------|
| Tiny shapes | Shapes only a few pixels wide. These are usually stray clicks. |
| Duplicate shapes | Two shapes of the same class on one picture that overlap almost exactly. |
| Near-identical pictures | Different files that look almost the same, such as frames from one video. Put these in one split, or your results will look better than they are. |
| Pictures with no shapes | Fine for background-only examples. A mistake in every other case. |
| Unbalanced classes | Classes with far fewer examples than the largest one. |

Each finding links to the shapes or pictures involved, so you can fix it right away.
