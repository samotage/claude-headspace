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
  host: 127.0.0.1
  port: 5055
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

### Commander (Input Bridge)

```yaml
commander:
  health_check_interval: 30
  socket_timeout: 2
  socket_path_prefix: /tmp/claudec-
```

- `health_check_interval` - Seconds between commander socket availability checks (1-3600, default: 30)
- `socket_timeout` - Timeout in seconds for socket operations (default: 2)
- `socket_path_prefix` - Path prefix for commander sockets. Must match the `claudec` binary's convention (default: `/tmp/claudec-`)

These settings control the [Input Bridge](input-bridge) feature. You only need to change them if you have a custom `claudec` setup or want to adjust how frequently availability is checked.

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
