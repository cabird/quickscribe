import { makeStyles, Text } from '@fluentui/react-components';

const useStyles = makeStyles({
  placeholder: {
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    justifyContent: 'center',
    height: '100%',
    gap: '16px',
  },
});

export function SearchPlaceholder() {
  const styles = useStyles();

  return (
    <div className={styles.placeholder}>
      <Text size={500}>RAG Search View</Text>
      <Text size={300}>Coming in Phase 2</Text>
    </div>
  );
}
