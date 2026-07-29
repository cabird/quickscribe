# In-Browser PrimeReact Development Guide

## Prerequisites

This guide assumes you have:
1. Read the **In-Browser React Guide** and understand the single namespace pattern
2. Access to the `primereact-standalone-bundle.umd.js` file
3. A basic Flask/Express server or similar to serve files with correct MIME types

## What This Guide Covers

How to use PrimeReact components in browser-only React applications without npm, webpack, or any build tools - just HTML, JavaScript, and the PrimeReact bundle.

---

## Core Concept: The PrimeReact Bundle

PrimeReact doesn't provide official browser UMD builds, but we've created a standalone bundle that exposes all PrimeReact components via a single global: `window.PrimeReactBundle`.

### What's Inside
- 40+ PrimeReact components (Button, InputText, Dropdown, DataTable, Dialog, etc.)
- All dependencies bundled (no separate react-transition-group needed)
- Optimized for React 18
- ~880KB (220KB gzipped)

---

## Setup

### 1. HTML Template

```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>My PrimeReact App</title>

    <!-- PrimeReact CSS (Required) -->
    <link rel="stylesheet" href="https://unpkg.com/primeicons/primeicons.css" />
    <link rel="stylesheet" href="https://unpkg.com/primereact/resources/themes/lara-light-blue/theme.css" />
    <link rel="stylesheet" href="https://unpkg.com/primereact/resources/primereact.min.css" />

    <!-- React 18 (Required - must load BEFORE PrimeReact bundle) -->
    <script crossorigin src="https://unpkg.com/react@18/umd/react.development.js"></script>
    <script crossorigin src="https://unpkg.com/react-dom@18/umd/react-dom.development.js"></script>

    <!-- PrimeReact Standalone Bundle -->
    <script src="/primereact-standalone-bundle.umd.js"></script>

    <!-- Babel Standalone for JSX -->
    <script src="https://unpkg.com/@babel/standalone/babel.min.js"></script>
</head>
<body>
    <div id="root"></div>

    <!-- Initialize your app namespace -->
    <script>window.MyApp = {};</script>

    <!-- Load your components -->
    <script type="text/babel" src="components/MyComponent.jsx"></script>
    <script type="text/babel" src="components/App.jsx"></script>

    <!-- Render -->
    <script type="text/babel">
        ReactDOM.createRoot(document.getElementById('root')).render(<MyApp.App />);
    </script>
</body>
</html>
```

### 2. Critical Loading Order

**MUST be in this exact order:**

1. ✅ **CSS files** (theme, core, icons)
2. ✅ **React & ReactDOM**
3. ✅ **PrimeReact bundle**
4. ✅ **Babel Standalone**
5. ✅ **Your namespace initialization**
6. ✅ **Your component files**
7. ✅ **Render call**

**Why:** The bundle expects React to be global, and your components expect PrimeReactBundle to be global.

---

## The Component Pattern

### Accessing PrimeReact Components

All PrimeReact components are available on `window.PrimeReactBundle`. Use destructuring at the top of each component file:

```javascript
// components/LoginForm.jsx
const { useState } = React;
const { Button, InputText, Password, Card } = PrimeReactBundle;

MyApp.LoginForm = function LoginForm() {
    const [username, setUsername] = useState('');
    const [password, setPassword] = useState('');

    const handleLogin = () => {
        console.log('Login:', username);
    };

    return (
        <Card title="Login">
            <div className="p-fluid">
                <div className="p-field" style={{ marginBottom: '1rem' }}>
                    <label htmlFor="username">Username</label>
                    <InputText
                        id="username"
                        value={username}
                        onChange={(e) => setUsername(e.target.value)}
                    />
                </div>

                <div className="p-field" style={{ marginBottom: '1rem' }}>
                    <label htmlFor="password">Password</label>
                    <Password
                        id="password"
                        value={password}
                        onChange={(e) => setPassword(e.target.value)}
                        feedback={false}
                    />
                </div>

                <Button
                    label="Login"
                    icon="pi pi-sign-in"
                    onClick={handleLogin}
                />
            </div>
        </Card>
    );
};
```

### Pattern Breakdown

1. **Destructure React hooks** from `React` (same as in-browser React guide)
2. **Destructure PrimeReact components** from `PrimeReactBundle` (new)
3. **Assign component to namespace** (`MyApp.LoginForm = ...`)
4. **Use components normally** in JSX

### Component Name Reference

Use the PascalCase component names exactly as documented in PrimeReact docs:

```javascript
const {
    // Form Components
    Button,
    InputText,
    InputTextarea,
    InputNumber,
    Dropdown,
    Calendar,
    Checkbox,
    RadioButton,
    MultiSelect,
    Password,

    // Data
    DataTable,
    Column,
    Tree,
    TreeTable,

    // Panels
    Card,
    Panel,
    Accordion,
    AccordionTab,
    Fieldset,
    Divider,
    Toolbar,

    // Overlays
    Dialog,
    Sidebar,
    OverlayPanel,
    Tooltip,
    ConfirmDialog,

    // Messages
    Toast,
    Message,
    Messages,

    // Feedback
    ProgressBar,
    ProgressSpinner,
    Tag,
    Badge,
    Avatar,
    Chip,

    // Menus
    Menu,
    Menubar,
    TabMenu,
    TabView,
    TabPanel,
    Steps,

    // File
    FileUpload
} = PrimeReactBundle;
```

---

## Common Patterns & Examples

### 1. Form with Validation

```javascript
const { useState } = React;
const { InputText, Button, Message } = PrimeReactBundle;

MyApp.ContactForm = function ContactForm() {
    const [email, setEmail] = useState('');
    const [error, setError] = useState('');

    const handleSubmit = (e) => {
        e.preventDefault();
        if (!email.includes('@')) {
            setError('Invalid email address');
            return;
        }
        console.log('Submit:', email);
    };

    return (
        <form onSubmit={handleSubmit}>
            {error && (
                <Message severity="error" text={error} style={{ marginBottom: '1rem' }} />
            )}

            <div className="p-field">
                <label htmlFor="email">Email</label>
                <InputText
                    id="email"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    className={error ? 'p-invalid' : ''}
                />
            </div>

            <Button label="Submit" type="submit" />
        </form>
    );
};
```

### 2. Data Table

```javascript
const { useState, useEffect } = React;
const { DataTable, Column, Button } = PrimeReactBundle;

MyApp.UserList = function UserList() {
    const [users, setUsers] = useState([]);

    useEffect(() => {
        // Fetch users from API
        fetch('/api/users')
            .then(res => res.json())
            .then(data => setUsers(data));
    }, []);

    const actionTemplate = (rowData) => {
        return (
            <Button
                icon="pi pi-pencil"
                className="p-button-rounded p-button-text"
                onClick={() => console.log('Edit', rowData)}
            />
        );
    };

    return (
        <DataTable value={users} responsiveLayout="scroll">
            <Column field="name" header="Name" sortable />
            <Column field="email" header="Email" sortable />
            <Column body={actionTemplate} header="Actions" />
        </DataTable>
    );
};
```

### 3. Tabs with Multiple Sections

```javascript
const { TabView, TabPanel, Card } = PrimeReactBundle;
const { UserList, SettingsPanel } = MyApp;

MyApp.Dashboard = function Dashboard() {
    return (
        <Card title="Dashboard">
            <TabView>
                <TabPanel header="Users" leftIcon="pi pi-users">
                    <UserList />
                </TabPanel>

                <TabPanel header="Settings" leftIcon="pi pi-cog">
                    <SettingsPanel />
                </TabPanel>
            </TabView>
        </Card>
    );
};
```

### 4. Dialog with State

```javascript
const { useState } = React;
const { Button, Dialog, InputText } = PrimeReactBundle;

MyApp.EditDialog = function EditDialog() {
    const [visible, setVisible] = useState(false);
    const [name, setName] = useState('');

    const handleSave = () => {
        console.log('Saving:', name);
        setVisible(false);
    };

    return (
        <>
            <Button
                label="Edit"
                icon="pi pi-pencil"
                onClick={() => setVisible(true)}
            />

            <Dialog
                header="Edit User"
                visible={visible}
                onHide={() => setVisible(false)}
                footer={
                    <div>
                        <Button label="Cancel" onClick={() => setVisible(false)} className="p-button-text" />
                        <Button label="Save" onClick={handleSave} />
                    </div>
                }
            >
                <div className="p-field">
                    <label htmlFor="name">Name</label>
                    <InputText
                        id="name"
                        value={name}
                        onChange={(e) => setName(e.target.value)}
                    />
                </div>
            </Dialog>
        </>
    );
};
```

### 5. Toast Notifications

```javascript
const { useRef } = React;
const { Button, Toast } = PrimeReactBundle;

MyApp.NotificationExample = function NotificationExample() {
    const toast = useRef(null);

    const showSuccess = () => {
        toast.current.show({
            severity: 'success',
            summary: 'Success',
            detail: 'Operation completed successfully',
            life: 3000
        });
    };

    const showError = () => {
        toast.current.show({
            severity: 'error',
            summary: 'Error',
            detail: 'Something went wrong',
            life: 5000
        });
    };

    return (
        <div>
            <Toast ref={toast} />
            <Button label="Success" onClick={showSuccess} className="p-button-success" />
            <Button label="Error" onClick={showError} className="p-button-danger" />
        </div>
    );
};
```

---

## Styling and Theming

### Using PrimeReact Themes

Change the theme by swapping the theme CSS URL:

```html
<!-- Light Blue (default) -->
<link rel="stylesheet" href="https://unpkg.com/primereact/resources/themes/lara-light-blue/theme.css" />

<!-- Dark Blue -->
<link rel="stylesheet" href="https://unpkg.com/primereact/resources/themes/lara-dark-blue/theme.css" />

<!-- Other themes -->
<!-- lara-light-indigo, lara-light-purple, lara-dark-indigo, etc. -->
```

### PrimeReact CSS Utilities

PrimeReact includes utility classes you can use:

```html
<!-- Fluid forms (full width inputs) -->
<div className="p-fluid">
    <InputText placeholder="Full width" />
</div>

<!-- Field spacing -->
<div className="p-field">
    <label>Label</label>
    <InputText />
</div>

<!-- Button styles -->
<Button className="p-button-success" />
<Button className="p-button-rounded" />
<Button className="p-button-text" />
<Button className="p-button-sm" />
```

### Custom Styles

Add your own CSS normally:

```html
<style>
    .my-card {
        max-width: 600px;
        margin: 2rem auto;
    }

    .p-field {
        margin-bottom: 1.5rem;
    }
</style>
```

---

## Server Configuration

### Flask Example

```python
import mimetypes
from flask import Flask, send_from_directory

# CRITICAL: Configure MIME type for .jsx BEFORE creating Flask app
mimetypes.add_type('application/javascript', '.jsx')

app = Flask(__name__, static_folder='.')

@app.route('/')
def index():
    return send_from_directory('.', 'index.html')

@app.route('/components/<path:filename>')
def serve_components(filename):
    return send_from_directory('components', filename)

@app.route('/primereact-standalone-bundle.umd.js')
def serve_bundle():
    return send_from_directory('.', 'primereact-standalone-bundle.umd.js')

if __name__ == '__main__':
    app.run(debug=True)
```

### Express Example

```javascript
const express = require('express');
const app = express();

app.use(express.static('.'));

app.get('/components/:filename', (req, res) => {
    res.type('application/javascript');
    res.sendFile(__dirname + '/components/' + req.params.filename);
});

app.listen(3000, () => console.log('Server running on port 3000'));
```

---

## Component Communication

### Parent-Child Props (Standard React)

```javascript
// Parent
const { UserForm } = MyApp;

MyApp.UserManager = function UserManager() {
    const handleUserSave = (userData) => {
        console.log('User saved:', userData);
    };

    return <UserForm onSave={handleUserSave} />;
};

// Child
const { Button, InputText } = PrimeReactBundle;

MyApp.UserForm = function UserForm({ onSave }) {
    const [name, setName] = useState('');

    const handleSubmit = () => {
        onSave({ name });
    };

    return (
        <div>
            <InputText value={name} onChange={(e) => setName(e.target.value)} />
            <Button label="Save" onClick={handleSubmit} />
        </div>
    );
};
```

### Shared State via Namespace (Simple Apps)

```javascript
// Shared state on namespace
window.MyApp.state = {
    user: null,
    listeners: []
};

MyApp.setUser = function(user) {
    MyApp.state.user = user;
    MyApp.state.listeners.forEach(fn => fn(user));
};

// Component using shared state
MyApp.UserDisplay = function UserDisplay() {
    const [user, setUser] = useState(MyApp.state.user);

    useEffect(() => {
        MyApp.state.listeners.push(setUser);
        return () => {
            MyApp.state.listeners = MyApp.state.listeners.filter(fn => fn !== setUser);
        };
    }, []);

    return <div>{user?.name || 'No user'}</div>;
};
```

---

## Common Pitfalls & Solutions

### ❌ Problem: PrimeReactBundle is undefined

**Cause:** Bundle didn't load or loaded after your components

**Solution:**
```html
<!-- React MUST come before bundle -->
<script src="react.js"></script>
<script src="react-dom.js"></script>
<script src="primereact-standalone-bundle.umd.js"></script> <!-- Then bundle -->
<script src="babel.js"></script> <!-- Then Babel -->
```

### ❌ Problem: Component not styled

**Cause:** Missing CSS files

**Solution:** Include all 3 CSS files:
```html
<link href=".../primeicons/primeicons.css" rel="stylesheet" />        <!-- Icons -->
<link href=".../themes/lara-light-blue/theme.css" rel="stylesheet" /> <!-- Theme -->
<link href=".../primereact.min.css" rel="stylesheet" />               <!-- Core -->
```

### ❌ Problem: 404 on .jsx files

**Cause:** Server not configured for .jsx MIME type

**Solution:** Configure server (see Flask example above)

### ❌ Problem: "Cannot read property 'XYZ' of undefined"

**Cause:** Trying to destructure a component that's not in the bundle

**Solution:** Check bundle contents or use a different component. The bundle includes only common components.

---

## Production Considerations

### For Production Deployment

1. **Switch to production React:**
   ```html
   <script src="https://unpkg.com/react@18/umd/react.production.min.js"></script>
   <script src="https://unpkg.com/react-dom@18/umd/react-dom.production.min.js"></script>
   ```

2. **Remove Babel Standalone:**
   - Pre-transpile JSX using Babel CLI
   - Or migrate to a proper build system

3. **Add CSP headers:**
   ```
   Content-Security-Policy: script-src 'self' https://unpkg.com;
   ```

4. **Consider bundle size:**
   - 880KB bundle may be large for production
   - Consider migration to Vite/Next.js for tree-shaking

### When to Migrate to a Build System

Move to Vite/Next.js when you need:
- Tree-shaking (only bundle components you use)
- TypeScript
- Code splitting
- Hot module replacement
- Better performance
- Server-side rendering

**Migration is easy:** The destructuring pattern mimics imports:

```javascript
// Before (browser)
const { Button } = PrimeReactBundle;

// After (Vite)
import { Button } from 'primereact/button';
```

JSX stays identical!

---

## Performance Tips

### 1. Load Bundle from CDN (Optional)

If you host the bundle on a CDN, it can be cached across projects:

```html
<script src="https://your-cdn.com/primereact-standalone-bundle.umd.js"></script>
```

### 2. Lazy Load Tabs

For tabbed interfaces, components render only when visible:

```javascript
const { TabView, TabPanel } = PrimeReactBundle;

MyApp.Dashboard = function Dashboard() {
    return (
        <TabView lazy> {/* Only renders active tab */}
            <TabPanel header="Heavy Component">
                <HeavyDataTable />
            </TabPanel>
        </TabView>
    );
};
```

### 3. Minimize Re-renders

Use React best practices (memo, useMemo, useCallback):

```javascript
const { useState, useMemo } = React;
const { DataTable } = PrimeReactBundle;

MyApp.OptimizedTable = function OptimizedTable({ data }) {
    const [filter, setFilter] = useState('');

    const filteredData = useMemo(() => {
        return data.filter(item => item.name.includes(filter));
    }, [data, filter]);

    return <DataTable value={filteredData} />;
};
```

---

## Complete Working Example

```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Todo App with PrimeReact</title>

    <!-- PrimeReact CSS -->
    <link rel="stylesheet" href="https://unpkg.com/primeicons/primeicons.css" />
    <link rel="stylesheet" href="https://unpkg.com/primereact/resources/themes/lara-light-blue/theme.css" />
    <link rel="stylesheet" href="https://unpkg.com/primereact/resources/primereact.min.css" />

    <!-- React 18 -->
    <script src="https://unpkg.com/react@18/umd/react.development.js"></script>
    <script src="https://unpkg.com/react-dom@18/umd/react-dom.development.js"></script>

    <!-- PrimeReact Bundle -->
    <script src="/primereact-standalone-bundle.umd.js"></script>

    <!-- Babel -->
    <script src="https://unpkg.com/@babel/standalone/babel.min.js"></script>
</head>
<body>
    <div id="root"></div>

    <script>window.TodoApp = {};</script>

    <script type="text/babel">
        const { useState } = React;
        const { Card, InputText, Button, Checkbox } = PrimeReactBundle;

        TodoApp.App = function App() {
            const [todos, setTodos] = useState([]);
            const [input, setInput] = useState('');

            const addTodo = () => {
                if (input.trim()) {
                    setTodos([...todos, { text: input, done: false }]);
                    setInput('');
                }
            };

            const toggleTodo = (index) => {
                const newTodos = [...todos];
                newTodos[index].done = !newTodos[index].done;
                setTodos(newTodos);
            };

            return (
                <div style={{ maxWidth: '600px', margin: '2rem auto' }}>
                    <Card title="My Todos">
                        <div style={{ display: 'flex', gap: '0.5rem', marginBottom: '1rem' }}>
                            <InputText
                                value={input}
                                onChange={(e) => setInput(e.target.value)}
                                onKeyPress={(e) => e.key === 'Enter' && addTodo()}
                                placeholder="Add a todo..."
                                style={{ flex: 1 }}
                            />
                            <Button
                                label="Add"
                                icon="pi pi-plus"
                                onClick={addTodo}
                            />
                        </div>

                        <div>
                            {todos.map((todo, i) => (
                                <div key={i} style={{ display: 'flex', alignItems: 'center', padding: '0.5rem', borderBottom: '1px solid #e0e0e0' }}>
                                    <Checkbox
                                        checked={todo.done}
                                        onChange={() => toggleTodo(i)}
                                    />
                                    <span style={{
                                        marginLeft: '0.5rem',
                                        textDecoration: todo.done ? 'line-through' : 'none'
                                    }}>
                                        {todo.text}
                                    </span>
                                </div>
                            ))}
                        </div>
                    </Card>
                </div>
            );
        };

        ReactDOM.createRoot(document.getElementById('root')).render(<TodoApp.App />);
    </script>
</body>
</html>
```

---

## Summary

### ✅ Do This
- Load CSS files (icons, theme, core)
- Load React before PrimeReact bundle
- Use destructuring to access components
- Follow single namespace pattern
- Configure server for .jsx MIME types

### ❌ Don't Do This
- Try to use ES6 imports (they won't work)
- Load bundle before React
- Skip CSS files
- Use component names that don't match PrimeReact docs
- Forget `type="text/babel"` on script tags

### 🎯 Perfect For
- Prototypes and demos
- Internal tools
- Learning PrimeReact
- Small to medium apps
- Environments without Node.js

### 🚫 Not Suitable For
- Large production apps
- Apps needing tree-shaking
- TypeScript projects
- Apps with strict performance requirements

---

## Getting the Bundle

The bundle is built using Vite from the PrimeReact npm package. To create your own or update:

```bash
cd primereact-browser-bundle
npm install
npm run build
# Output: dist/primereact-standalone-bundle.umd.js
```

See `SETUP_COMPLETE.md` for full bundle build instructions.

---

## Resources

- [PrimeReact Documentation](https://primereact.org/) - Component API reference
- [In-Browser React Guide](./IN_BROWSER_REACT_GUIDE.md) - Foundation concepts
- [PrimeIcons](https://primereact.org/icons/) - Available icons
- [PrimeReact Themes](https://primereact.org/theming/) - Styling options

---

**Happy coding without the build complexity!** 🎉
