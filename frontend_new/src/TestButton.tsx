import { Button } from '@mantine/core';

export function TestButton() {
  return (
    <div style={{ padding: '50px', display: 'flex', flexDirection: 'column', gap: '20px' }}>
      <h2>Button Hover Test</h2>
      
      {/* Test 1: Basic glass button */}
      <Button className="glass-button" color="violet">
        Glass Button Test
      </Button>
      
      {/* Test 2: Basic button without glass class */}
      <Button color="violet">
        Normal Button Test
      </Button>
      
      {/* Test 3: Button with inline styles */}
      <Button 
        color="violet"
        style={{
          transition: 'all 0.3s ease',
          '&:hover': {
            transform: 'translateY(-3px)',
            boxShadow: '0 12px 40px rgba(138, 43, 226, 0.4)'
          }
        } as any}
      >
        Inline Style Button
      </Button>
      
      {/* Test 4: Plain HTML button with glass class */}
      <button className="glass-button" style={{ padding: '10px 20px', fontSize: '16px' }}>
        HTML Button with Glass Class
      </button>
      
      {/* Test 5: Plain HTML button with inline hover */}
      <button 
        style={{ 
          padding: '10px 20px', 
          fontSize: '16px',
          transition: 'all 0.3s ease',
          backgroundColor: '#8a2be2'
        }}
        onMouseEnter={(e) => {
          e.currentTarget.style.transform = 'translateY(-3px)';
          e.currentTarget.style.boxShadow = '0 12px 40px rgba(138, 43, 226, 0.4)';
        }}
        onMouseLeave={(e) => {
          e.currentTarget.style.transform = 'translateY(0)';
          e.currentTarget.style.boxShadow = 'none';
        }}
      >
        JS Hover Button
      </button>
    </div>
  );
}