# Gophish Integration for SecBoard

This module provides complete integration with the Gophish phishing simulation platform, allowing you to manage campaigns, templates, landing pages, and monitor results directly from the SecBoard interface.

## Features

### 🔧 Server Management
- Add and configure multiple Gophish servers
- Encrypted API key storage
- Connection testing and status monitoring
- Server-specific data isolation

### 📧 Campaign Management
- Create and launch phishing campaigns
- Monitor campaign status and results
- View detailed statistics and metrics
- Export campaign data

### 📝 Content Management
- Email template management
- Landing page configuration
- Sending profile setup
- Target group management

### 📊 Monitoring & Analytics
- Real-time campaign events
- Detailed statistics and metrics
- Event timeline and user actions
- Success rate tracking

### 🔄 Data Synchronization
- Automatic background synchronization
- Manual sync options
- Selective data sync (campaigns, templates, etc.)
- Sync logging and error handling

## Installation

1. The module is already included in your SecBoard installation
2. Run migrations to create the database tables:
   ```bash
   python manage.py migrate app_gophish
   ```

## Configuration

### 1. Add Gophish Servers

1. Navigate to **Gophish → Servers**
2. Click **Add Server**
3. Fill in the required information:
   - **Server Name**: A friendly name for identification
   - **Base URL**: Full URL to your Gophish server (e.g., `https://gophish.example.com`)
   - **API Key**: API key from your Gophish server settings
   - **Active**: Enable/disable the server

### 2. Get API Key from Gophish

1. Log into your Gophish server
2. Go to **Settings → API**
3. Generate a new API key
4. Copy the key and paste it in SecBoard

### 3. Synchronize Data

1. Go to **Gophish → Sync**
2. Select your server and sync type
3. Click **Start Synchronization**

## Usage

### Creating Campaigns

1. Navigate to **Gophish → Campaigns**
2. Click **Create Campaign**
3. Fill in campaign details:
   - Select server and target groups
   - Choose email template and landing page
   - Configure sending profile
   - Set launch date (optional)
4. Save and launch when ready

### Monitoring Results

1. View campaign dashboard for overview
2. Click on specific campaigns for detailed metrics
3. Monitor real-time events and user interactions
4. Export data for reporting

### Managing Content

- **Templates**: Create and edit email templates
- **Landing Pages**: Configure phishing landing pages
- **Sending Profiles**: Set up SMTP configurations
- **Groups**: Manage target email groups

## API Integration

The module uses the official Gophish REST API to communicate with your Gophish servers. All API calls are:

- Authenticated using API keys
- Encrypted in transit (HTTPS)
- Logged for audit purposes
- Rate-limited to prevent overload

## Security Features

- **Encrypted Storage**: All sensitive data (API keys, passwords) are encrypted
- **Secure Communication**: Only HTTPS connections are supported
- **Access Control**: Integration with SecBoard's permission system
- **Audit Logging**: All actions are logged for security auditing

## Celery Tasks

The integration includes several background tasks:

- **Automatic Sync**: Runs every 15 minutes to sync active servers
- **Data Cleanup**: Removes old events and sync logs
- **Campaign Monitoring**: Updates campaign status and results

## Models

### Core Models

- `GophishServer`: Server configurations and connection details
- `GophishCampaign`: Campaign data and results
- `GophishTemplate`: Email templates
- `GophishLandingPage`: Landing page configurations
- `GophishSendingProfile`: SMTP sending profiles
- `GophishGroup`: Target email groups
- `GophishEvent`: Campaign events and user interactions
- `GophishSyncLog`: Synchronization history and logs

## URLs

The integration provides the following URL patterns:

- `/app_gophish/` - Dashboard
- `/app_gophish/servers/` - Server management
- `/app_gophish/campaigns/` - Campaign management
- `/app_gophish/templates/` - Template management
- `/app_gophish/landing-pages/` - Landing page management
- `/app_gophish/sending-profiles/` - Sending profile management
- `/app_gophish/groups/` - Group management
- `/app_gophish/sync/` - Synchronization

## Admin Interface

All models are available in the Django admin interface at `/secboard_admin/app_gophish/` with:

- Comprehensive list views with filtering
- Inline editing for related objects
- Bulk operations
- Export functionality

## Troubleshooting

### Connection Issues

1. Verify the server URL is correct and accessible
2. Check that the API key is valid and has proper permissions
3. Ensure the server is not behind a firewall blocking API access
4. Test the connection using the server detail page

### Sync Issues

1. Check sync logs for error messages
2. Verify server connectivity and API key validity
3. Ensure the Gophish server is running and accessible
4. Check Celery worker status for background tasks

### Performance Issues

1. Limit the number of active servers
2. Use selective sync instead of full sync when possible
3. Monitor database size and clean up old events
4. Check server resources and API rate limits

## Support

For issues related to the Gophish integration:

1. Check the sync logs for error messages
2. Verify server configurations and connectivity
3. Review the Django logs for detailed error information
4. Ensure all dependencies are properly installed

## Contributing

When contributing to the Gophish integration:

1. Follow the existing code structure and patterns
2. Add comprehensive tests for new features
3. Update documentation for any changes
4. Ensure backward compatibility when possible
5. Follow security best practices for API integrations
