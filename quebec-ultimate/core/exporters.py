"""OSIN CHAIN QUEBEC ULTIMATE - Exporters V2 - Ghost1o1
Supports JSON / HTML report exports with footprint + geo movement timeline.
"""
import json
import html as html_lib
from typing import Dict, List, Optional
from pathlib import Path
from datetime import datetime, timezone


class ReportExporter:
    def __init__(self, graph_manager=None, export_dir: str = "exports"):
        self.graph = graph_manager
        self.export_dir = Path(export_dir)
        self.export_dir.mkdir(parents=True, exist_ok=True)

    def _utcnow(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def _ts_slug(self) -> str:
        return datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")

    def export_json(self, entity_id: Optional[str] = None,
                    footprint: Optional[Dict] = None) -> Dict:
        if not self.graph or not self.graph.connected:
            return {"error": "Graph not connected", "data": []}

        if entity_id:
            try:
                neighborhood = self.graph.get_neighborhood(entity_id, depth=5)
            except Exception:
                neighborhood = {"nodes": [], "edges": []}
            data = {
                "export_type": "subgraph",
                "root_entity_id": entity_id,
                "nodes": neighborhood.get("nodes", []),
                "edges": neighborhood.get("edges", []),
            }
        else:
            try:
                data = self.graph.full_export()
            except Exception as e:
                data = {"nodes": [], "edges": [], "error": str(e)}
            data["export_type"] = "full_graph"

        if footprint:
            data["footprint"] = footprint

        data["metadata"] = {
            "exported_at": self._utcnow(),
            "tool": "OSIN CHAIN QUEBEC ULTIMATE",
            "author": "Ghost1o1",
            "version": "1.1.0-ultimate",
            "footprint_included": bool(footprint),
        }

        filename = f"osin_export_{self._ts_slug()}.json"
        filepath = self.export_dir / filename
        try:
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False, default=str)
            data["filepath"] = str(filepath)
        except Exception as e:
            data["filepath_error"] = str(e)

        return data

    def export_pdf(self, entity_id: Optional[str] = None,
                   footprint: Optional[Dict] = None) -> str:
        if not self.graph or not self.graph.connected:
            return ""

        if entity_id:
            try:
                neighborhood = self.graph.get_neighborhood(entity_id, depth=5)
                entities = neighborhood.get("nodes", [])
                relations = neighborhood.get("edges", [])
                root = self.graph.get_entity(entity_id)
            except Exception:
                entities, relations, root = [], [], None
        else:
            try:
                full = self.graph.full_export()
                entities = full.get("nodes", [])
                relations = full.get("edges", [])
            except Exception:
                entities, relations = [], []
            root = entities[0] if entities else None

        try:
            from reportlab.lib.pagesizes import A4, letter
            from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
            from reportlab.lib.units import cm, mm
            from reportlab.lib.colors import HexColor, black, white, grey
            from reportlab.lib.enums import TA_LEFT, TA_RIGHT, TA_CENTER
            from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer,
                                            Table, TableStyle, PageBreak,
                                            Image as RLImage, KeepTogether)
            from reportlab.pdfgen import canvas
            return self._build_pdf_reportlab(root, entities, relations, footprint,
                                             A4, getSampleStyleSheet, ParagraphStyle,
                                             cm, mm, HexColor, black, white, grey,
                                             TA_LEFT, TA_RIGHT, TA_CENTER,
                                             SimpleDocTemplate, Paragraph, Spacer,
                                             Table, TableStyle, PageBreak, KeepTogether)
        except ImportError:
            html_content = self._build_html(root, entities, relations, footprint)
            filename = f"osin_report_{self._ts_slug()}.html"
            filepath = self.export_dir / filename
            try:
                with open(filepath, "w", encoding="utf-8") as f:
                    f.write(html_content)
            except Exception:
                return ""
            return str(filepath)

    def _build_pdf_reportlab(self, root, entities, relations, footprint, *mods) -> str:
        from pathlib import Path as _P
        (A4, getSampleStyleSheet, ParagraphStyle, cm, mm, HexColor,
         black, white, grey, TA_LEFT, TA_RIGHT, TA_CENTER,
         SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
         PageBreak, KeepTogether) = mods

        filename = f"osin_report_{self._ts_slug()}.pdf"
        filepath = self.export_dir / filename

        doc = SimpleDocTemplate(
            str(filepath), pagesize=A4,
            leftMargin=1.8*cm, rightMargin=1.8*cm,
            topMargin=1.5*cm, bottomMargin=1.5*cm,
            title="OSIN CHAIN QUEBEC ULTIMATE — Rapport OSINT",
            author="Ghost1o1",
        )

        styles = getSampleStyleSheet()
        title_style = ParagraphStyle('GhostTitle', parent=styles['Title'],
            fontName='Helvetica-Bold', fontSize=22, textColor=HexColor('#ffd60a'),
            alignment=TA_LEFT, spaceAfter=4*mm, leading=26)
        subtitle_style = ParagraphStyle('GhostSub', parent=styles['Normal'],
            fontName='Helvetica', fontSize=9, textColor=HexColor('#94a3b8'),
            spaceAfter=8*mm, alignment=TA_LEFT)
        h2_style = ParagraphStyle('GhostH2', parent=styles['Heading2'],
            fontName='Helvetica-Bold', fontSize=14, textColor=HexColor('#4ecdc4'),
            spaceBefore=8*mm, spaceAfter=3*mm, leftIndent=0)
        h3_style = ParagraphStyle('GhostH3', parent=styles['Heading3'],
            fontName='Helvetica-Bold', fontSize=11, textColor=HexColor('#a78bfa'),
            spaceBefore=4*mm, spaceAfter=2*mm)
        body_style = ParagraphStyle('GhostBody', parent=styles['Normal'],
            fontName='Helvetica', fontSize=9, textColor=HexColor('#e8edf5'),
            leading=12, spaceAfter=2*mm)
        small_style = ParagraphStyle('GhostSmall', parent=styles['Normal'],
            fontName='Helvetica', fontSize=7, textColor=HexColor('#64748b'),
            leading=9)
        cell_style = ParagraphStyle('GhostCell', parent=styles['Normal'],
            fontName='Helvetica', fontSize=7.5, textColor=HexColor('#e8edf5'),
            leading=10)
        cell_dim = ParagraphStyle('GhostCellDim', parent=styles['Normal'],
            fontName='Helvetica', fontSize=7, textColor=HexColor('#94a3b8'),
            leading=9)
        sig_style = ParagraphStyle('GhostSig', parent=styles['Normal'],
            fontName='Helvetica-Oblique', fontSize=8, textColor=HexColor('#64748b'),
            alignment=TA_RIGHT, spaceBefore=10*mm)

        story = []

        # ─── HEADER ───
        story.append(Paragraph("OSIN CHAIN QUEBEC ULTIMATE", title_style))
        root_val = str(root.get('value', 'Graph Complet')) if root else 'Graph Complet'
        meta_line = (f"Entité racine: <b><font color='#ffd60a'>{html_lib.escape(root_val[:80])}</font></b>  "
                     f"&nbsp;&nbsp;Généré: {datetime.now(timezone.utc).strftime('%d/%m/%Y %H:%M:%S')} UTC")
        story.append(Paragraph(meta_line, subtitle_style))

        # ─── STATS ───
        type_counts = {}
        for e in entities:
            etype = str(e.get('type', 'unknown'))
            type_counts[etype] = type_counts.get(etype, 0) + 1

        stats_data = [
            [Paragraph(f"<b><font color='#4ecdc4' size='18'>{len(entities)}</font></b><br/><font color='#94a3b8' size='7'>ENTITÉS</font>", body_style),
             Paragraph(f"<b><font color='#4ecdc4' size='18'>{len(relations)}</font></b><br/><font color='#94a3b8' size='7'>RELATIONS</font>", body_style),
             Paragraph(f"<b><font color='#4ecdc4' size='18'>{len(type_counts)}</font></b><br/><font color='#94a3b8' size='7'>TYPES</font>", body_style),
             Paragraph(f"<b><font color='#4ecdc4' size='18'>1.1.0</font></b><br/><font color='#94a3b8' size='7'>VERSION</font>", body_style),
             Paragraph(f"<b><font color='#4ecdc4' size='18'>{html_lib.escape(self._ts_slug())}</font></b><br/><font color='#94a3b8' size='7'>TIMESTAMP</font>", body_style)]
        ]
        stats_table = Table(stats_data, colWidths=[3.5*cm]*5)
        stats_table.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,-1), HexColor('#1a2335')),
            ('BOX', (0,0), (-1,-1), 1, HexColor('#2a3550')),
            ('INNERGRID', (0,0), (-1,-1), 0.5, HexColor('#2a3550')),
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
            ('ALIGN', (0,0), (-1,-1), 'CENTER'),
            ('TOPPADDING', (0,0), (-1,-1), 8),
            ('BOTTOMPADDING', (0,0), (-1,-1), 8),
        ]))
        story.append(stats_table)
        story.append(Spacer(1, 5*mm))

        # ─── FOOTPRINT (mouvement GPS) ───
        if footprint:
            story.append(Paragraph("📍 Empreinte & Mouvement", h2_style))
            trail = footprint.get('movement_trail', [])
            segs = footprint.get('movement_segments', [])
            uniq = footprint.get('unique_locations', [])
            dist = footprint.get('total_distance_km', 0)

            fp_stats = [
                [Paragraph(f"<b><font color='#a78bfa' size='14'>{footprint.get('snapshots_count',0)}</font></b><br/><font color='#94a3b8' size='7'>SNAPSHOTS</font>", body_style),
                 Paragraph(f"<b><font color='#a78bfa' size='14'>{len(trail)}</font></b><br/><font color='#94a3b8' size='7'>POINTS GPS</font>", body_style),
                 Paragraph(f"<b><font color='#a78bfa' size='14'>{len(uniq)}</font></b><br/><font color='#94a3b8' size='7'>LIEUX UNIQUES</font>", body_style),
                 Paragraph(f"<b><font color='#a78bfa' size='14'>{dist:.0f} km</font></b><br/><font color='#94a3b8' size='7'>DISTANCE</font>", body_style),
                 Paragraph(f"<b><font color='#a78bfa' size='14'>{len(segs)}</font></b><br/><font color='#94a3b8' size='7'>SEGMENTS</font>", body_style),
                 Paragraph(f"<b><font color='#a78bfa' size='14'>{footprint.get('unique_entities_seen',0)}</font></b><br/><font color='#94a3b8' size='7'>ENTITÉS VUES</font>", body_style)]
            ]
            fp_tbl = Table(fp_stats, colWidths=[2.9*cm]*6)
            fp_tbl.setStyle(TableStyle([
                ('BACKGROUND', (0,0), (-1,-1), HexColor('#0d1228')),
                ('BOX', (0,0), (-1,-1), 0.5, HexColor('#a78bfa')),
                ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
                ('ALIGN', (0,0), (-1,-1), 'CENTER'),
                ('TOPPADDING', (0,0), (-1,-1), 6),
                ('BOTTOMPADDING', (0,0), (-1,-1), 6),
            ]))
            story.append(fp_tbl)
            story.append(Spacer(1, 4*mm))

            if trail:
                story.append(Paragraph("Trajectoire (30 premiers points)", h3_style))
                trail_rows = [[Paragraph("<b><font color='#94a3b8'>#</font></b>", cell_style),
                               Paragraph("<b><font color='#94a3b8'>Source</font></b>", cell_style),
                               Paragraph("<b><font color='#94a3b8'>Lat</font></b>", cell_style),
                               Paragraph("<b><font color='#94a3b8'>Lon</font></b>", cell_style),
                               Paragraph("<b><font color='#94a3b8'>Timestamp</font></b>", cell_style)]]
                for i, p in enumerate(trail[:30]):
                    trail_rows.append([
                        Paragraph(str(i+1), cell_style),
                        Paragraph(html_lib.escape(str(p.get('source',''))[:25]), cell_style),
                        Paragraph(f"{p.get('lat', 0):.4f}", cell_dim),
                        Paragraph(f"{p.get('lon', 0):.4f}", cell_dim),
                        Paragraph(html_lib.escape(str(p.get('timestamp',''))[:19]), cell_dim),
                    ])
                tt = Table(trail_rows, colWidths=[1*cm, 4*cm, 2.5*cm, 2.5*cm, 5*cm])
                tt.setStyle(TableStyle([
                    ('BACKGROUND', (0,0), (-1,0), HexColor('#1a2335')),
                    ('ROWBACKGROUNDS', (0,1), (-1,-1), [HexColor('#0d1228'), HexColor('#131a30')]),
                    ('GRID', (0,0), (-1,-1), 0.3, HexColor('#2a3550')),
                    ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
                    ('TOPPADDING', (0,0), (-1,-1), 3),
                    ('BOTTOMPADDING', (0,0), (-1,-1), 3),
                ]))
                story.append(tt)
                story.append(Spacer(1, 4*mm))

            if segs:
                story.append(Paragraph("Segments de mouvement", h3_style))
                seg_rows = [[Paragraph("<b><font color='#94a3b8'>De</font></b>", cell_style),
                             Paragraph("<b><font color='#94a3b8'>→</font></b>", cell_style),
                             Paragraph("<b><font color='#94a3b8'>Vers</font></b>", cell_style),
                             Paragraph("<b><font color='#94a3b8'>Distance</font></b>", cell_style),
                             Paragraph("<b><font color='#94a3b8'>Bearing</font></b>", cell_style),
                             Paragraph("<b><font color='#94a3b8'>Vitesse</font></b>", cell_style)]]
                for s in segs[:20]:
                    f_val = html_lib.escape(str(s.get('from',{}).get('value',''))[:30])
                    t_val = html_lib.escape(str(s.get('to',{}).get('value',''))[:30])
                    seg_rows.append([
                        Paragraph(f_val, cell_style),
                        Paragraph("→", cell_style),
                        Paragraph(t_val, cell_style),
                        Paragraph(f"{s.get('distance_km', 0):.1f} km", cell_dim),
                        Paragraph(f"{s.get('bearing_deg', 0):.0f}° {s.get('bearing_compass', '')}", cell_dim),
                        Paragraph(s.get('speed_category', 'stationary'), cell_dim),
                    ])
                st = Table(seg_rows, colWidths=[4.2*cm, 0.8*cm, 4.2*cm, 2.2*cm, 2.4*cm, 2.2*cm])
                st.setStyle(TableStyle([
                    ('BACKGROUND', (0,0), (-1,0), HexColor('#1a2335')),
                    ('ROWBACKGROUNDS', (0,1), (-1,-1), [HexColor('#0d1228'), HexColor('#131a30')]),
                    ('GRID', (0,0), (-1,-1), 0.3, HexColor('#2a3550')),
                    ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
                    ('TOPPADDING', (0,0), (-1,-1), 3),
                    ('BOTTOMPADDING', (0,0), (-1,-1), 3),
                ]))
                story.append(st)

        # ─── ENTITÉS PAR TYPE ───
        story.append(Spacer(1, 4*mm))
        story.append(Paragraph("📊 Entités par Type", h2_style))
        type_rows = [[Paragraph("<b><font color='#94a3b8'>Type</font></b>", cell_style),
                      Paragraph("<b><font color='#94a3b8'>Nombre</font></b>", cell_style)]]
        for t, c in sorted(type_counts.items(), key=lambda x: -x[1]):
            type_rows.append([Paragraph(f"<font color='#4ecdc4'>{html_lib.escape(t)}</font>", cell_style),
                              Paragraph(str(c), cell_style)])
        type_tbl = Table(type_rows, colWidths=[10*cm, 5*cm])
        type_tbl.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), HexColor('#1a2335')),
            ('ROWBACKGROUNDS', (0,1), (-1,-1), [HexColor('#0d1228'), HexColor('#131a30')]),
            ('GRID', (0,0), (-1,-1), 0.3, HexColor('#2a3550')),
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
            ('TOPPADDING', (0,0), (-1,-1), 3),
            ('BOTTOMPADDING', (0,0), (-1,-1), 3),
        ]))
        story.append(type_tbl)

        # ─── ENTITÉS DÉCOUVERTES ───
        story.append(PageBreak())
        story.append(Paragraph("🔍 Entités Découvertes", h2_style))
        ent_header = [Paragraph("<b><font color='#94a3b8'>Type</font></b>", cell_style),
                      Paragraph("<b><font color='#94a3b8'>Valeur</font></b>", cell_style),
                      Paragraph("<b><font color='#94a3b8'>Conf.</font></b>", cell_style),
                      Paragraph("<b><font color='#94a3b8'>Source</font></b>", cell_style)]
        ent_rows = [ent_header]
        for e in entities[:80]:
            etype = html_lib.escape(str(e.get('type', '')))
            val = html_lib.escape(str(e.get('value', ''))[:90])
            conf = float(e.get('confidence', 0) or 0)
            src = html_lib.escape(str(e.get('source', ''))[:40])
            ent_rows.append([
                Paragraph(f"<font color='#4ecdc4'>{etype}</font>", cell_style),
                Paragraph(f"<font color='#ffd60a'>{val}</font>", cell_style),
                Paragraph(f"{conf:.0%}", cell_dim),
                Paragraph(src, cell_dim),
            ])
        ent_tbl = Table(ent_rows, colWidths=[3*cm, 7.5*cm, 1.5*cm, 5*cm], repeatRows=1)
        ent_tbl.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), HexColor('#1a2335')),
            ('ROWBACKGROUNDS', (0,1), (-1,-1), [HexColor('#0d1228'), HexColor('#131a30')]),
            ('GRID', (0,0), (-1,-1), 0.3, HexColor('#2a3550')),
            ('VALIGN', (0,0), (-1,-1), 'TOP'),
            ('TOPPADDING', (0,0), (-1,-1), 3),
            ('BOTTOMPADDING', (0,0), (-1,-1), 3),
        ]))
        story.append(ent_tbl)

        # ─── RELATIONS ───
        story.append(Spacer(1, 5*mm))
        story.append(Paragraph("🔗 Relations", h2_style))
        rel_header = [Paragraph("<b><font color='#94a3b8'>Type</font></b>", cell_style),
                      Paragraph("<b><font color='#94a3b8'>Source</font></b>", cell_style),
                      Paragraph("<b><font color='#94a3b8'>→</font></b>", cell_style),
                      Paragraph("<b><font color='#94a3b8'>Cible</font></b>", cell_style),
                      Paragraph("<b><font color='#94a3b8'>Preuve</font></b>", cell_style)]
        rel_rows = [rel_header]
        for r in relations[:80]:
            rtype = html_lib.escape(str(r.get('type', '')).replace('_', ' '))
            src_id = html_lib.escape(str(r.get('source', ''))[:40])
            tgt_id = html_lib.escape(str(r.get('target', ''))[:40])
            ev = html_lib.escape(str(r.get('evidence', ''))[:60])
            rel_rows.append([
                Paragraph(f"<font color='#a78bfa'>{rtype}</font>", cell_style),
                Paragraph(src_id, cell_dim),
                Paragraph("→", cell_dim),
                Paragraph(tgt_id, cell_dim),
                Paragraph(ev, cell_dim),
            ])
        rel_tbl = Table(rel_rows, colWidths=[3.5*cm, 4*cm, 0.8*cm, 4*cm, 5*cm], repeatRows=1)
        rel_tbl.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), HexColor('#1a2335')),
            ('ROWBACKGROUNDS', (0,1), (-1,-1), [HexColor('#0d1228'), HexColor('#131a30')]),
            ('GRID', (0,0), (-1,-1), 0.3, HexColor('#2a3550')),
            ('VALIGN', (0,0), (-1,-1), 'TOP'),
            ('TOPPADDING', (0,0), (-1,-1), 3),
            ('BOTTOMPADDING', (0,0), (-1,-1), 3),
        ]))
        story.append(rel_tbl)

        # ─── FOOTER ───
        story.append(Spacer(1, 8*mm))
        story.append(Paragraph(
            f"Signé <b><font color='#ffd60a'>Ghost1o1</font></b> — "
            f"OSIN CHAIN QUEBEC ULTIMATE v1.1.0-ultimate — "
            f"Généré via reportlab — Confidentiel",
            sig_style))

        # ─── PAGE FOOTER ───
        def _on_page(canv, doc):
            canv.saveState()
            canv.setFont('Helvetica', 7)
            canv.setFillColor(HexColor('#64748b'))
            canv.drawString(1.8*cm, 0.8*cm, "OSIN CHAIN QUEBEC ULTIMATE — Confidentiel")
            canv.drawRightString(A4[0]-1.8*cm, 0.8*cm, f"Page {doc.page}")
            canv.restoreState()

        try:
            doc.build(story, onFirstPage=_on_page, onLaterPages=_on_page)
        except Exception as e:
            return ""
        return str(filepath)

    def export_png(self, entity_id: Optional[str] = None) -> str:
        data = self.export_json(entity_id)
        filename = f"osin_graph_{self._ts_slug()}.json"
        filepath = self.export_dir / filename
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False, default=str)
        return str(filepath)

    def _build_html(self, root, entities, relations, footprint) -> str:
        root_val = html_lib.escape(str(root.get("value", "Graph Complet"))) if root else "Graph Complet"
        total_e = len(entities)
        total_r = len(relations)
        type_counts: Dict[str, int] = {}
        for e in entities:
            etype = str(e.get("type", "unknown"))
            type_counts[etype] = type_counts.get(etype, 0) + 1

        entities_rows = []
        for e in entities[:100]:
            etype = html_lib.escape(str(e.get("type", "")))
            val = html_lib.escape(str(e.get("value", ""))[:100])
            conf = float(e.get("confidence", 0) or 0)
            src = html_lib.escape(str(e.get("source", "")))
            entities_rows.append(
                f"<tr><td><span class='badge badge-type'>{etype}</span></td>"
                f"<td>{val}</td><td>{conf:.0%}</td><td><code>{src}</code></td></tr>"
            )
        entities_html = "\n".join(entities_rows)

        rels_rows = []
        for r in relations[:100]:
            rtype = html_lib.escape(str(r.get("type", "")).replace("_", " "))
            src_id = html_lib.escape(str(r.get("source", ""))[:30])
            tgt_id = html_lib.escape(str(r.get("target", ""))[:30])
            ev = html_lib.escape(str(r.get("evidence", ""))[:80])
            rels_rows.append(
                f"<tr><td>{rtype}</td><td><code>{src_id}</code> → <code>{tgt_id}</code></td>"
                f"<td>{ev}</td></tr>"
            )
        rels_html = "\n".join(rels_rows)

        type_rows = "".join(
            f"<tr><td><span class='badge badge-type'>{html_lib.escape(t)}</span></td><td>{c}</td></tr>"
            for t, c in sorted(type_counts.items(), key=lambda x: -x[1])
        )

        # Footprint block
        fp_block = ""
        if footprint:
            fp = footprint
            trail = fp.get("movement_trail", [])
            segs = fp.get("movement_segments", [])
            uniq = fp.get("unique_locations", [])
            dist = fp.get("total_distance_km", 0)
            fp_block = f"""
            <h2>📍 Empreinte & Mouvement</h2>
            <div class="stats">
                <div class="stat"><div class="stat-value">{fp.get('snapshots_count', 0)}</div><div class="stat-label">Snapshots</div></div>
                <div class="stat"><div class="stat-value">{len(trail)}</div><div class="stat-label">Points GPS</div></div>
                <div class="stat"><div class="stat-value">{len(uniq)}</div><div class="stat-label">Lieux uniques</div></div>
                <div class="stat"><div class="stat-value">{dist:.0f} km</div><div class="stat-label">Distance totale</div></div>
                <div class="stat"><div class="stat-value">{len(segs)}</div><div class="stat-label">Segments</div></div>
                <div class="stat"><div class="stat-value">{fp.get('unique_entities_seen', 0)}</div><div class="stat-label">Entités vues</div></div>
            </div>
            <h3>Trajectoire</h3>
            <table>
                <tr><th>#</th><th>Source</th><th>Lat</th><th>Lon</th><th>Timestamp</th></tr>
                {''.join(
                    f"<tr><td>{i+1}</td><td>{html_lib.escape(str(p.get('source','')))}</td>"
                    f"<td>{p.get('lat', 0):.4f}</td><td>{p.get('lon', 0):.4f}</td>"
                    f"<td>{html_lib.escape(str(p.get('timestamp','')))}</td></tr>"
                    for i, p in enumerate(trail[:30])
                )}
            </table>
            <h3>Segments de mouvement</h3>
            <table>
                <tr><th>De</th><th>→</th><th>Vers</th><th>Distance</th><th>Bearing</th><th>Vitesse</th></tr>
                {''.join(
                    f"<tr><td>{html_lib.escape(str(s['from'].get('value',''))[:30])}</td>"
                    f"<td>→</td>"
                    f"<td>{html_lib.escape(str(s['to'].get('value',''))[:30])}</td>"
                    f"<td>{s.get('distance_km', 0):.1f} km</td>"
                    f"<td>{s.get('bearing_deg', 0):.0f}° ({s.get('bearing_compass', '')})</td>"
                    f"<td>{s.get('speed_category', 'stationary')}</td></tr>"
                    for s in segs[:30]
                )}
            </table>
            """

        return f"""<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="UTF-8">
<title>OSIN CHAIN QUEBEC ULTIMATE — Rapport</title>
<style>
* {{ box-sizing: border-box; }}
body {{ font-family: 'Inter','Segoe UI',sans-serif; background: #0a0f1e; color: #e8edf5; padding: 40px; margin: 0; }}
h1 {{ color: #ffd60a; border-bottom: 3px solid #2a3550; padding-bottom: 12px; margin-top: 0; }}
h2 {{ color: #4da6ff; margin-top: 30px; border-left: 4px solid #4da6ff; padding-left: 12px; }}
h3 {{ color: #94a3b8; margin-top: 20px; }}
table {{ width: 100%; border-collapse: collapse; margin: 15px 0; font-size: 0.9em; }}
th {{ background: #1a2335; padding: 10px; text-align: left; border-bottom: 2px solid #2a3550; color: #94a3b8; }}
td {{ padding: 8px 10px; border-bottom: 1px solid #1a2335; }}
tr:hover td {{ background: #1a2335; }}
.stats {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(120px, 1fr)); gap: 16px; margin: 20px 0; }}
.stat {{ background: #1a2335; padding: 16px; border-radius: 8px; text-align: center; border: 1px solid #2a3550; }}
.stat-value {{ font-size: 1.6em; color: #4da6ff; font-weight: bold; }}
.stat-label {{ font-size: 0.8em; color: #94a3b8; text-transform: uppercase; letter-spacing: 1px; }}
.badge {{ padding: 2px 8px; border-radius: 4px; font-size: 0.85em; }}
.badge-type {{ background: #4da6ff22; color: #4da6ff; border: 1px solid #4da6ff44; }}
code {{ background: #0a0f1e; color: #ffd60a; padding: 1px 4px; border-radius: 2px; font-size: 0.85em; }}
.signature {{ text-align: right; color: #94a3b8; font-size: 0.8em; margin-top: 50px; padding-top: 20px; border-top: 1px solid #2a3550; }}
</style>
</head>
<body>
<h1>🏴‍☠️ OSIN CHAIN QUEBEC ULTIMATE</h1>
<p>Entité racine: <strong>{root_val}</strong></p>
<p>Généré le: {datetime.now(timezone.utc).strftime('%d/%m/%Y à %H:%M:%S')} UTC</p>

<div class="stats">
    <div class="stat"><div class="stat-value">{total_e}</div><div class="stat-label">Entités</div></div>
    <div class="stat"><div class="stat-value">{total_r}</div><div class="stat-label">Relations</div></div>
    <div class="stat"><div class="stat-value">{len(type_counts)}</div><div class="stat-label">Types</div></div>
</div>

{fp_block}

<h2>📊 Entités par Type</h2>
<table><tr><th>Type</th><th>Nombre</th></tr>{type_rows}</table>

<h2>🔍 Entités Découvertes</h2>
<table><tr><th>Type</th><th>Valeur</th><th>Confiance</th><th>Source</th></tr>{entities_html}</table>

<h2>🔗 Relations</h2>
<table><tr><th>Type</th><th>Connexion</th><th>Preuve</th></tr>{rels_html}</table>

<div class="signature">
    Signé <strong>Ghost1o1</strong> — OSIN CHAIN QUEBEC ULTIMATE v1.1.0-ultimate
</div>
</body>
</html>"""
