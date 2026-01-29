# Configuration

Claude Headspace is configured via `config.yaml` in the project root.

## Editing Configuration

You can edit configuration in two ways:

1. **Config Page** - Click **Config** in navigation for a web-based editor
2. **Direct Edit** - Edit `config.yaml` directly with any text editor

## Configuration Options

### Server Settings

```yaml
server:
  host: 0.0.0.0
  port: 5050
  debug: false
```

- `host` - Interface to bind to (0.0.0.0 for all interfaces)
- `port` - Port number for the web server
- `debug` - Enable Flask debug mode (development only)

### Database Settings

```yaml
database:
  path: data/headspace.db
```

- `path` - Location of the SQLite database file

### Monitored Projects

```yaml
projects:
  - name: MyProject
    path: /path/to/project
```

Each project needs:
- `name` - Display name shown in dashboard
- `path` - Absolute path to the project directory

### Objective

```yaml
objective: "Current priority description"
```

The global objective used for agent prioritization.

### Notifications

```yaml
notifications:
  enabled: true
  sound: true
```

- `enabled` - Enable/disable macOS notifications
- `sound` - Play sound with notifications

## Config Page Features

The web-based config editor provides:

- Syntax validation before save
- Preview of changes
- Reset to last saved version
- Error messages for invalid YAML

## After Changes

Configuration changes take effect:

- **Immediately** - For objective and notifications
- **On restart** - For server and database settings
