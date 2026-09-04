# LEDO

LEDO is an isolated temporary application hosted by the existing CulinEire
Django process. It deliberately has no dependency on CulinEire templates,
models, or navigation.

## Preview

- URL: `/ledo/`
- Access: authenticated staff users only
- Feature flag: `LEDO_ENABLED=True`
- Search indexing: disabled by the page's robots metadata

The feature flag defaults to `False`, so merging or deploying the code alone
does not expose the application. Enable the flag in the server environment and
restart the Django application when a private preview is wanted.
