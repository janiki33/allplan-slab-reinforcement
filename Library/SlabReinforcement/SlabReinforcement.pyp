<?xml version='1.0' encoding='UTF-8'?>
<Element xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:noNamespaceSchemaLocation="https://pythonparts.allplan.com/2026/schemas/PythonPart.xsd">
  <Script>
    <Name>SlabReinforcement\SlabReinforcement.py</Name>
    <Title>SlabReinforcement</Title>
    <Version>0.3</Version>
    <ReadLastInput>True</ReadLastInput>
  </Script>
  <Constants>
    <Constant>
      <Name>INPUT_MODE_INPUT</Name>
      <Value>1</Value>
      <ValueType>Integer</ValueType>
    </Constant>
    <Constant>
      <Name>INPUT_MODE_CREATION</Name>
      <Value>2</Value>
      <ValueType>Integer</ValueType>
    </Constant>
  </Constants>
  <Page>
    <Name>GeometryPage</Name>
    <Text>Geometrie</Text>
    <Parameters>
      <Parameter>
        <Name>InputExpander</Name>
        <Text>Eingabe</Text>
        <ValueType>Expander</ValueType>
        <Parameters>
          <Parameter>
            <Name>InputMethod</Name>
            <Text>Eingabemodus</Text>
            <Value>Rechteck (Drag)</Value>
            <ValueList>Rechteck (Drag)|Polygon zeichnen|Element wählen</ValueList>
            <ValueType>StringComboBox</ValueType>
          </Parameter>
        </Parameters>
      </Parameter>
      <Parameter>
        <Name>GeometryExpander</Name>
        <Text>Plattenabmessungen</Text>
        <ValueType>Expander</ValueType>
        <Parameters>
          <Parameter>
            <Name>SlabLength</Name>
            <Text>Länge (X)</Text>
            <Value>5000</Value>
            <MinValue>500</MinValue>
            <ValueType>Length</ValueType>
            <Visible>InputMethod == "Rechteck (Drag)"</Visible>
          </Parameter>
          <Parameter>
            <Name>SlabWidth</Name>
            <Text>Breite (Y)</Text>
            <Value>4000</Value>
            <MinValue>500</MinValue>
            <ValueType>Length</ValueType>
            <Visible>InputMethod == "Rechteck (Drag)"</Visible>
          </Parameter>
          <Parameter>
            <Name>SlabThickness</Name>
            <Text>Dicke</Text>
            <Value>250</Value>
            <MinValue>80</MinValue>
            <ValueType>Length</ValueType>
          </Parameter>
        </Parameters>
      </Parameter>
      <Parameter>
        <Name>PlacementExpander</Name>
        <Text>Verlegung</Text>
        <ValueType>Expander</ValueType>
        <Parameters>
          <Parameter>
            <Name>OuterLayerDirection</Name>
            <Text>Äußere Lagen</Text>
            <Value>X-Richtung</Value>
            <ValueList>X-Richtung|Y-Richtung</ValueList>
            <ValueType>StringComboBox</ValueType>
          </Parameter>
          <Parameter>
            <Name>EdgeZonesActive</Name>
            <Text>Randverdichtung</Text>
            <Value>False</Value>
            <ValueType>CheckBox</ValueType>
          </Parameter>
          <Parameter>
            <Name>EdgeZoneLength</Name>
            <Text>Zonenlänge</Text>
            <Value>1000</Value>
            <MinValue>100</MinValue>
            <ValueType>Length</ValueType>
            <Visible>EdgeZonesActive</Visible>
          </Parameter>
          <Parameter>
            <Name>EdgeZoneSpacing</Name>
            <Text>Stababstand in der Zone</Text>
            <Value>100</Value>
            <MinValue>25</MinValue>
            <ValueType>Length</ValueType>
            <Visible>EdgeZonesActive</Visible>
          </Parameter>
        </Parameters>
      </Parameter>
    </Parameters>
  </Page>
  <Page>
    <Name>BottomLayerPage</Name>
    <Text>Bewehrung unten</Text>
    <Parameters>
      <Parameter>
        <Name>AllLayersExpander</Name>
        <Text>Alle Lagen</Text>
        <ValueType>Expander</ValueType>
        <Parameters>
          <Parameter>
            <Name>SameDiameterForAll</Name>
            <Text>Alle Lagen gleicher Durchmesser</Text>
            <Value>False</Value>
            <ValueType>CheckBox</ValueType>
          </Parameter>
          <Parameter>
            <Name>RowAll</Name>
            <Text>Alle Lagen</Text>
            <ValueType>Row</ValueType>
            <Visible>SameDiameterForAll == True</Visible>
            <Parameters>
              <Parameter>
                <Name>DiaAll</Name>
                <Text>ø</Text>
                <Value>12</Value>
                <ValueType>ReinfBarDiameter</ValueType>
              </Parameter>
              <Parameter>
                <Name>SpacingAll</Name>
                <Text>a</Text>
                <Value>150</Value>
                <ValueType>Length</ValueType>
              </Parameter>
            </Parameters>
          </Parameter>
        </Parameters>
      </Parameter>
      <Parameter>
        <Name>BottomXExpander</Name>
        <Text>Untere Lage X-Richtung</Text>
        <ValueType>Expander</ValueType>
        <Parameters>
          <Parameter>
            <Name>BottomXDiameter</Name>
            <Text>Durchmesser</Text>
            <Value>12</Value>
            <ValueType>ReinfBarDiameter</ValueType>
            <Visible>SameDiameterForAll == False</Visible>
          </Parameter>
          <Parameter>
            <Name>BottomXSpacing</Name>
            <Text>Stababstand</Text>
            <Value>150</Value>
            <MinValue>25</MinValue>
            <ValueType>Length</ValueType>
            <Visible>SameDiameterForAll == False</Visible>
          </Parameter>
          <Parameter>
            <Name>BottomXCover</Name>
            <Text>Betondeckung unten</Text>
            <Value>25</Value>
            <ValueType>ReinfConcreteCover</ValueType>
          </Parameter>
          <Parameter>
            <Name>BottomXSteelGrade</Name>
            <Text>Stahlgüte</Text>
            <Value>4</Value>
            <ValueType>ReinfSteelGrade</ValueType>
          </Parameter>
        </Parameters>
      </Parameter>
      <Parameter>
        <Name>BottomYExpander</Name>
        <Text>Untere Lage Y-Richtung</Text>
        <ValueType>Expander</ValueType>
        <Parameters>
          <Parameter>
            <Name>BottomYDiameter</Name>
            <Text>Durchmesser</Text>
            <Value>12</Value>
            <ValueType>ReinfBarDiameter</ValueType>
            <Visible>SameDiameterForAll == False</Visible>
          </Parameter>
          <Parameter>
            <Name>BottomYSpacing</Name>
            <Text>Stababstand</Text>
            <Value>150</Value>
            <MinValue>25</MinValue>
            <ValueType>Length</ValueType>
            <Visible>SameDiameterForAll == False</Visible>
          </Parameter>
          <Parameter>
            <Name>BottomYCover</Name>
            <Text>Betondeckung unten</Text>
            <Value>25</Value>
            <ValueType>ReinfConcreteCover</ValueType>
          </Parameter>
          <Parameter>
            <Name>BottomYSteelGrade</Name>
            <Text>Stahlgüte</Text>
            <Value>4</Value>
            <ValueType>ReinfSteelGrade</ValueType>
          </Parameter>
        </Parameters>
      </Parameter>
    </Parameters>
  </Page>
  <Page>
    <Name>TopLayerPage</Name>
    <Text>Bewehrung oben</Text>
    <Parameters>
      <Parameter>
        <Name>TopXExpander</Name>
        <Text>Obere Lage X-Richtung</Text>
        <ValueType>Expander</ValueType>
        <Parameters>
          <Parameter>
            <Name>TopXDiameter</Name>
            <Text>Durchmesser</Text>
            <Value>10</Value>
            <ValueType>ReinfBarDiameter</ValueType>
            <Visible>SameDiameterForAll == False</Visible>
          </Parameter>
          <Parameter>
            <Name>TopXSpacing</Name>
            <Text>Stababstand</Text>
            <Value>150</Value>
            <MinValue>25</MinValue>
            <ValueType>Length</ValueType>
            <Visible>SameDiameterForAll == False</Visible>
          </Parameter>
          <Parameter>
            <Name>TopXCover</Name>
            <Text>Betondeckung oben</Text>
            <Value>30</Value>
            <ValueType>ReinfConcreteCover</ValueType>
          </Parameter>
          <Parameter>
            <Name>TopXSteelGrade</Name>
            <Text>Stahlgüte</Text>
            <Value>4</Value>
            <ValueType>ReinfSteelGrade</ValueType>
          </Parameter>
        </Parameters>
      </Parameter>
      <Parameter>
        <Name>TopYExpander</Name>
        <Text>Obere Lage Y-Richtung</Text>
        <ValueType>Expander</ValueType>
        <Parameters>
          <Parameter>
            <Name>TopYDiameter</Name>
            <Text>Durchmesser</Text>
            <Value>10</Value>
            <ValueType>ReinfBarDiameter</ValueType>
            <Visible>SameDiameterForAll == False</Visible>
          </Parameter>
          <Parameter>
            <Name>TopYSpacing</Name>
            <Text>Stababstand</Text>
            <Value>150</Value>
            <MinValue>25</MinValue>
            <ValueType>Length</ValueType>
            <Visible>SameDiameterForAll == False</Visible>
          </Parameter>
          <Parameter>
            <Name>TopYCover</Name>
            <Text>Betondeckung oben</Text>
            <Value>30</Value>
            <ValueType>ReinfConcreteCover</ValueType>
          </Parameter>
          <Parameter>
            <Name>TopYSteelGrade</Name>
            <Text>Stahlgüte</Text>
            <Value>4</Value>
            <ValueType>ReinfSteelGrade</ValueType>
          </Parameter>
        </Parameters>
      </Parameter>
    </Parameters>
  </Page>
  <Page>
    <Name>SidesPage</Name>
    <Text>Seiten</Text>
    <Parameters>
      <Parameter>
        <Name>OverlapExpander</Name>
        <Text>Stoß</Text>
        <ValueType>Expander</ValueType>
        <Parameters>
          <Parameter>
            <Name>OverlapFactor</Name>
            <Text>Stoßlänge (x ø)</Text>
            <Value>50</Value>
            <MinValue>1</MinValue>
            <ValueType>Integer</ValueType>
          </Parameter>
        </Parameters>
      </Parameter>
      <Parameter>
        <Name>SidesExpander</Name>
        <Text>Randausbildung je Kante</Text>
        <ValueType>Expander</ValueType>
        <Parameters>
          <Parameter>
            <Name>SideLeft</Name>
            <Text>Links (X=0)</Text>
            <Value>Keine</Value>
            <ValueList>Randbügel|Anschlusseisen|Separate Anschlusseisen|Keine</ValueList>
            <ValueType>StringComboBox</ValueType>
          </Parameter>
          <Parameter>
            <Name>SideRight</Name>
            <Text>Rechts (X=Länge)</Text>
            <Value>Keine</Value>
            <ValueList>Randbügel|Anschlusseisen|Separate Anschlusseisen|Keine</ValueList>
            <ValueType>StringComboBox</ValueType>
          </Parameter>
          <Parameter>
            <Name>SideBottom</Name>
            <Text>Unten (Y=0)</Text>
            <Value>Keine</Value>
            <ValueList>Randbügel|Anschlusseisen|Separate Anschlusseisen|Keine</ValueList>
            <ValueType>StringComboBox</ValueType>
          </Parameter>
          <Parameter>
            <Name>SideTop</Name>
            <Text>Oben (Y=Breite)</Text>
            <Value>Keine</Value>
            <ValueList>Randbügel|Anschlusseisen|Separate Anschlusseisen|Keine</ValueList>
            <ValueType>StringComboBox</ValueType>
          </Parameter>
        </Parameters>
      </Parameter>
    </Parameters>
  </Page>
  <Page>
    <Name>OpeningPage</Name>
    <Text>Öffnung</Text>
    <Parameters>
      <Parameter>
        <Name>OpeningExpander</Name>
        <Text>Rechteckige Öffnung</Text>
        <ValueType>Expander</ValueType>
        <Parameters>
          <Parameter>
            <Name>HasOpening</Name>
            <Text>Öffnung berücksichtigen</Text>
            <Value>False</Value>
            <ValueType>CheckBox</ValueType>
          </Parameter>
          <Parameter>
            <Name>OpeningX</Name>
            <Text>Abstand X vom Plattenursprung</Text>
            <Value>1500</Value>
            <MinValue>0</MinValue>
            <ValueType>Length</ValueType>
            <Visible>HasOpening</Visible>
          </Parameter>
          <Parameter>
            <Name>OpeningY</Name>
            <Text>Abstand Y vom Plattenursprung</Text>
            <Value>1200</Value>
            <MinValue>0</MinValue>
            <ValueType>Length</ValueType>
            <Visible>HasOpening</Visible>
          </Parameter>
          <Parameter>
            <Name>OpeningWidth</Name>
            <Text>Öffnungsbreite (X)</Text>
            <Value>800</Value>
            <MinValue>100</MinValue>
            <ValueType>Length</ValueType>
            <Visible>HasOpening</Visible>
          </Parameter>
          <Parameter>
            <Name>OpeningHeight</Name>
            <Text>Öffnungslänge (Y)</Text>
            <Value>1000</Value>
            <MinValue>100</MinValue>
            <ValueType>Length</ValueType>
            <Visible>HasOpening</Visible>
          </Parameter>
        </Parameters>
      </Parameter>
      <Parameter>
        <Name>EdgeReinfExpander</Name>
        <Text>Randverstärkung Öffnung</Text>
        <ValueType>Expander</ValueType>
        <Visible>HasOpening</Visible>
        <Parameters>
          <Parameter>
            <Name>EdgeReinfActive</Name>
            <Text>Randverstärkung erzeugen</Text>
            <Value>True</Value>
            <ValueType>CheckBox</ValueType>
          </Parameter>
          <Parameter>
            <Name>EdgeBarDiameter</Name>
            <Text>Durchmesser Zulagestäbe</Text>
            <Value>12</Value>
            <ValueType>ReinfBarDiameter</ValueType>
            <Visible>EdgeReinfActive</Visible>
          </Parameter>
          <Parameter>
            <Name>EdgeBarCount</Name>
            <Text>Stabanzahl je Kante</Text>
            <Value>2</Value>
            <MinValue>1</MinValue>
            <MaxValue>6</MaxValue>
            <ValueType>Integer</ValueType>
            <Visible>EdgeReinfActive</Visible>
          </Parameter>
          <Parameter>
            <Name>EdgeBarSpacing</Name>
            <Text>Stababstand Zulagestäbe</Text>
            <Value>50</Value>
            <MinValue>25</MinValue>
            <ValueType>Length</ValueType>
            <Visible>EdgeReinfActive</Visible>
          </Parameter>
          <Parameter>
            <Name>LapLength</Name>
            <Text>Übergreifungslänge</Text>
            <Value>800</Value>
            <MinValue>0</MinValue>
            <ValueType>Length</ValueType>
            <Visible>EdgeReinfActive</Visible>
          </Parameter>
        </Parameters>
      </Parameter>
    </Parameters>
  </Page>
  <Page>
    <Name>CommonPage</Name>
    <Text>Allgemein</Text>
    <Parameters>
      <Parameter>
        <Name>MaterialExpander</Name>
        <Text>Material</Text>
        <ValueType>Expander</ValueType>
        <Parameters>
          <Parameter>
            <Name>ConcreteGrade</Name>
            <Text>Betongüte</Text>
            <Value>-1</Value>
            <ValueType>ReinfConcreteGrade</ValueType>
          </Parameter>
          <Parameter>
            <Name>SideCover</Name>
            <Text>Betondeckung seitlich</Text>
            <Value>25</Value>
            <ValueType>ReinfConcreteCover</ValueType>
          </Parameter>
          <Parameter>
            <Name>MinBarLength</Name>
            <Text>Mindeststablänge</Text>
            <Value>300</Value>
            <MinValue>0</MinValue>
            <ValueType>Length</ValueType>
          </Parameter>
        </Parameters>
      </Parameter>
      <Parameter>
        <Name>FormatExpander</Name>
        <Text>Format</Text>
        <ValueType>Expander</ValueType>
        <Parameters>
          <Parameter>
            <Name>CommonProp</Name>
            <Text/>
            <Value/>
            <ValueType>CommonProperties</ValueType>
          </Parameter>
        </Parameters>
      </Parameter>
      <Parameter>
        <Name>LayerExpander</Name>
        <Text>Layer Bewehrung (0 = aktueller Layer)</Text>
        <ValueType>Expander</ValueType>
        <Parameters>
          <Parameter>
            <Name>LayerBottomX</Name>
            <Text>Layer untere Lage X</Text>
            <Value>0</Value>
            <ValueType>Layer</ValueType>
          </Parameter>
          <Parameter>
            <Name>LayerBottomY</Name>
            <Text>Layer untere Lage Y</Text>
            <Value>0</Value>
            <ValueType>Layer</ValueType>
          </Parameter>
          <Parameter>
            <Name>LayerTopX</Name>
            <Text>Layer obere Lage X</Text>
            <Value>0</Value>
            <ValueType>Layer</ValueType>
          </Parameter>
          <Parameter>
            <Name>LayerTopY</Name>
            <Text>Layer obere Lage Y</Text>
            <Value>0</Value>
            <ValueType>Layer</ValueType>
          </Parameter>
          <Parameter>
            <Name>LayerStirrupX</Name>
            <Text>Layer Randbügel links/rechts</Text>
            <Value>0</Value>
            <ValueType>Layer</ValueType>
          </Parameter>
          <Parameter>
            <Name>LayerStirrupY</Name>
            <Text>Layer Randbügel unten/oben</Text>
            <Value>0</Value>
            <ValueType>Layer</ValueType>
          </Parameter>
        </Parameters>
      </Parameter>
      <Parameter>
        <Name>ElementCreationExpander</Name>
        <Text>Elementerzeugung</Text>
        <ValueType>Expander</ValueType>
        <Parameters>
          <Parameter>
            <Name>IsPythonPart</Name>
            <Text>Als PythonPart erzeugen</Text>
            <Value>True</Value>
            <ValueType>CheckBox</ValueType>
          </Parameter>
        </Parameters>
      </Parameter>
    </Parameters>
  </Page>
  <Page>
    <Name>HiddenPage</Name>
    <Text/>
    <Parameters>
      <Parameter>
        <Name>InputMode</Name>
        <Text>Input mode</Text>
        <Value/>
        <ValueType>Integer</ValueType>
      </Parameter>
    </Parameters>
  </Page>
</Element>
