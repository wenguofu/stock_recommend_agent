import { describe, it, expect } from 'vitest';
import {
  Card, Button, Space, Typography, Spin, Alert, Empty,
  Table, Tag, Modal, Select, Segmented, Checkbox,
} from 'antd';

describe('antd imports', () => {
  it('all imports are defined', () => {
    expect(Card).toBeDefined();
    expect(Button).toBeDefined();
    expect(Space).toBeDefined();
    expect(Typography).toBeDefined();
    expect(Spin).toBeDefined();
    expect(Alert).toBeDefined();
    expect(Empty).toBeDefined();
    expect(Table).toBeDefined();
    expect(Tag).toBeDefined();
    expect(Modal).toBeDefined();
    expect(Select).toBeDefined();
    expect(Segmented).toBeDefined();
    expect(Checkbox).toBeDefined();
  });
});
