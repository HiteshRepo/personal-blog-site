# Personal Blog

This is a personal blog site built with Hugo and deployed on Netlify.

## Development Automation

This project includes automation tools to simplify content creation and deployment.

### Local Development (Makefile)

A Makefile is provided with the following commands:

```bash
# Start local development server
make serve

# Build site locally
make build

# Clean build artifacts
make clean

# Create a new post (specify section)
make new-post TITLE='My Post Title' SECTION=technical

# Create a new technical post
make new-tech TITLE='My Tech Post'

# Create a new non-technical post
make new-nontech TITLE='My Non-Tech Post'

# Create a new AI-related post
make new-ai TITLE='My AI Post'

# Publish a draft post
make publish FILE=path/to/post.md

# Preview the production site locally
make preview

# Check for common issues
make check
```

Run `make help` to see all available commands.

### Deployment

Deployment is handled automatically by Netlify when changes are pushed to the main branch.

Additionally, a GitHub Actions workflow is set up to build the site on every push to main and pull request. This ensures the site builds correctly before deployment.

## Content Creation Workflow

1. Create a new post using the Makefile:

   ```bash
   # For a technical post
   make new-tech TITLE='My New Technical Post'
   
   # For a non-technical post
   make new-nontech TITLE='My New Non-Technical Post'
   
   # For an AI-related post
   make new-ai TITLE='My New AI Post'
   ```

2. Edit the generated Markdown file in the content directory.

3. Preview your changes locally:

   ```bash
   make serve
   ```

4. When ready to publish, change the draft status:

   ```bash
   make publish FILE=content/technical/my-new-technical-post.md
   ```

5. Preview the production version of the site:

   ```bash
   make preview
   ```

6. Commit and push your changes to GitHub:

   ```bash
   git add .
   git commit -m "Add new post: My New Technical Post"
   git push
   ```

7. Netlify will automatically deploy the updated site.

## Custom Archetypes

This project includes custom archetypes (templates) for different types of content:

- **Default**: General-purpose template for any content
- **Technical**: Template for technical posts with sections for code examples and troubleshooting
- **Non-technical**: Template for opinion pieces and non-technical content
- **AI**: Specialized template for AI-related posts with sections for technical details and mathematical formulas
